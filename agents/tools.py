"""Simulated tools the agents call where the prototype has no real system to call.

Each function stands in for one tool from the report (observability API, project
board, Git repository, CI runner, deploy pipeline). They are seeded and
deterministic, so the same ticket always produces the same result and every
number can be reproduced. Seeds come from crc32 (never Python's hash(), which
changes between runs). Outputs are labelled as simulated wherever they are shown.
"""
from __future__ import annotations

import random
import zlib
from typing import Any

from agents.scout_log_program import summarize

# --- Topology: six services, one per data node --------------------------------------------
SERVICES = ("api-gateway", "order-service", "payment-db", "auth-service", "search-service",
            "notification-service")
NODE_SERVICE = {f"node-{index}": service for index, service in enumerate(SERVICES, start=1)}
# The call chain a request for each product area travels through (caller first).
COMPONENT_CHAINS = {
    "payment": ("api-gateway", "order-service", "payment-db"),
    "promo": ("api-gateway", "order-service", "payment-db"),
    "login": ("api-gateway", "auth-service", "notification-service"),
    "account": ("api-gateway", "auth-service", "order-service"),
    "search": ("api-gateway", "search-service", "order-service"),
    "delivery": ("api-gateway", "order-service", "notification-service"),
    "notification": ("api-gateway", "order-service", "notification-service"),
    "app": ("api-gateway", "order-service", "search-service"),
    "other": ("api-gateway", "order-service", "payment-db"),
}
# Where the simulated fault sits for each area (the "true" root cause in the simulation).
COMPONENT_FAULT = {"payment": "payment-db", "promo": "order-service", "login": "notification-service",
                   "account": "auth-service", "search": "search-service", "delivery": "notification-service",
                   "notification": "notification-service", "app": "api-gateway", "other": "order-service"}
# Nominal size of each node's local log store in MB (the report assumes 1,365 MB per busy node).
NODE_LOG_MB = {"api-gateway": 1365, "order-service": 1365, "payment-db": 1365, "auth-service": 1365,
               "search-service": 1365, "notification-service": 30}
CRITICAL_SERVICES = {"payment-db", "auth-service", "order-service"}

# What "healthy" looks like: mean, spread and SLO limit per service and metric.
DEFAULT_SLO_BASELINES: dict[str, dict[str, dict[str, Any]]] = {
    service: {
        "latency_p95_ms": {"window_minutes": 10080, "mean": mean, "std": mean * 0.12, "slo": slo, "unit": "ms"},
        "error_rate": {"window_minutes": 10080, "mean": 0.004, "std": 0.002, "slo": 0.02, "unit": "ratio"},
    }
    for service, mean, slo in (("api-gateway", 180, 500), ("order-service", 240, 600), ("payment-db", 310, 800),
                               ("auth-service", 150, 450), ("search-service", 260, 700),
                               ("notification-service", 120, 400))
}


def stable_seed(*parts: Any) -> int:
    return zlib.crc32("|".join(str(part) for part in parts).encode("utf-8"))


def rng(*parts: Any) -> random.Random:
    return random.Random(stable_seed(*parts))


# --- Observability: raw node logs and their aggregates ------------------------------------
def node_logs(service: str, seed: int, component: str, records: int = 600) -> list[dict[str, Any]]:
    """Raw request logs as they sit on one node. These never leave the node.

    They include a fake customer e-mail per request (on a reserved test domain), so
    tests can prove that only aggregates, never raw rows, cross the node boundary.
    """
    generator = rng("logs", service, seed, component)
    faulty = COMPONENT_FAULT.get(component) == service
    base = DEFAULT_SLO_BASELINES[service]["latency_p95_ms"]["mean"] * 0.6
    rows = []
    for index in range(records):
        latency = generator.gauss(base * (3.4 if faulty else 1.0), base * 0.25)
        failed = generator.random() < (0.11 if faulty else 0.004)
        rows.append({"minute": index % 30, "latency_ms": round(max(5.0, latency), 1),
                     "status": 500 if failed else 200,
                     "customer_email": f"user{generator.randrange(10_000)}@users.example.net"})
    return rows


def standard_aggregates(service: str, logs: list[dict[str, Any]]) -> dict[str, Any]:
    """The node's built-in exporter: the same aggregates a Scout-Log bundle computes."""
    return summarize({"service": service, "local_logs": logs})


def z_score(value: float, mean: float, std: float) -> float:
    return round((value - mean) / std, 2) if std else 0.0


# --- Monitoring: telemetry series for the dashboard and the post-release check ------------
def telemetry(scenario: str = "flash_sale", seed: int = 42, minutes: int = 60,
              anomaly_z: float = 3.0) -> dict[str, Any]:
    """One hour of per-minute metrics for three services, with anomalies flagged by z-score.

    In the flash-sale scenario payment-db slows down and fails more often between
    minutes 20 and 32; afterwards a fix ships as a 5% -> 25% -> 50% -> 100% canary.
    """
    watched = ("api-gateway", "order-service", "payment-db")
    services, anomalies = [], []
    for service in watched:
        generator = rng("telemetry", scenario, seed, service)
        latency_base = DEFAULT_SLO_BASELINES[service]["latency_p95_ms"]
        error_base = DEFAULT_SLO_BASELINES[service]["error_rate"]
        latency, errors, rps = [], [], []
        for minute in range(minutes):
            incident = scenario == "flash_sale" and service == "payment-db" and 20 <= minute <= 32
            surge = scenario == "flash_sale" and 18 <= minute <= 36
            latency.append(round(generator.gauss(latency_base["mean"], latency_base["std"] * 0.6)
                                 * (6.5 if incident else 1.0), 1))
            errors.append(round(max(0.0, generator.gauss(error_base["mean"], error_base["std"] * 0.5))
                                + (0.06 if incident else 0.0), 4))
            rps.append(round(generator.gauss(420, 25) * (3.2 if surge else 1.0), 1))
        series = {"latency_p95_ms": latency, "error_rate": errors, "rps": rps}
        for metric in ("latency_p95_ms", "error_rate"):
            base = DEFAULT_SLO_BASELINES[service][metric]
            flagged = [minute for minute, value in enumerate(series[metric])
                       if z_score(value, base["mean"], base["std"]) >= anomaly_z or value > base["slo"]]
            if flagged:
                peak = max(flagged, key=lambda minute: series[metric][minute])
                anomalies.append({
                    "anomaly_id": f"ANO-{scenario}-{seed}-{service}-{metric}", "service": service,
                    "metric": metric, "start_minute": flagged[0], "end_minute": flagged[-1],
                    "peak_minute": peak, "peak_value": series[metric][peak], "baseline_mean": base["mean"],
                    "slo": base["slo"], "z": z_score(series[metric][peak], base["mean"], base["std"])})
        services.append({"service": service, "node_id": next(node for node, name in NODE_SERVICE.items()
                                                               if name == service),
                         "series": series, "slo": {metric: DEFAULT_SLO_BASELINES[service][metric]["slo"]
                                                   for metric in ("latency_p95_ms", "error_rate")}})
    canary = ([{"minute": 40, "percent": 5, "status": "healthy"}, {"minute": 46, "percent": 25, "status": "healthy"},
               {"minute": 50, "percent": 50, "status": "healthy"},
               {"minute": 54, "percent": 100, "status": "healthy", "needs_human": True}]
              if scenario == "flash_sale" else [])
    return {"scenario": scenario, "seed": seed, "simulated": True, "step_seconds": 60,
            "services": services, "anomalies": anomalies, "canary_steps": canary}


def post_release_metrics(service: str, seed: int, regression: bool) -> dict[str, float]:
    """30 minutes after a release: healthy unless a known regression shipped."""
    generator = rng("post-release", service, seed)
    base = DEFAULT_SLO_BASELINES[service]
    latency = generator.gauss(base["latency_p95_ms"]["mean"], base["latency_p95_ms"]["std"] * 0.5)
    error = max(0.0, generator.gauss(base["error_rate"]["mean"], base["error_rate"]["std"] * 0.4))
    if regression:
        latency, error = latency * 2.8, error + 0.035
    return {"latency_p95_ms": round(latency, 1), "error_rate": round(error, 4)}


# --- Planning, repository, CI and deployment ------------------------------------------------
def project_board(seed: int) -> dict[str, Any]:
    generator = rng("board", seed)
    return {"sprint": "Sprint 14", "capacity_hours_left": generator.randrange(18, 60),
            "open_items": generator.randrange(9, 24)}


REPOSITORY_FILES = {
    "payment-db": ("services/payment/db_pool.py", "services/payment/checkout_handler.py"),
    "order-service": ("services/order/create_order.py", "services/order/promo_rules.py"),
    "auth-service": ("services/auth/session.py", "services/auth/otp_sender.py"),
    "notification-service": ("services/notify/sms_gateway.py", "services/notify/retry_queue.py"),
    "search-service": ("services/search/query_cache.py", "services/search/ranking.py"),
    "api-gateway": ("services/gateway/rate_limits.py", "services/gateway/routes.py"),
}
FIX_IDEAS = {
    "payment-db": "raise the connection-pool limit and add a retry with backoff on PaymentSheet confirm",
    "order-service": "make order creation idempotent so a retried payment cannot create a ghost order",
    "auth-service": "extend the session timeout and fix the token refresh race",
    "notification-service": "fail over to the backup SMS provider when the primary queue backs up",
    "search-service": "cache popular queries and cap the ranking fan-out",
    "api-gateway": "relax the per-user rate limit for checkout routes during sales",
}


def repository_context(service: str) -> dict[str, Any]:
    return {"repository": "t2d-commerce (simulated)", "files": list(REPOSITORY_FILES[service])}


def draft_diff(service: str, ticket_id: str, inject_secret: bool = False) -> dict[str, Any]:
    """A small, readable fake diff for the suspected service (no real repository is touched)."""
    files = list(REPOSITORY_FILES[service])
    generator = rng("diff", service, ticket_id)
    additions, deletions = generator.randrange(18, 64), generator.randrange(4, 22)
    lines = [f"--- a/{files[0]}", f"+++ b/{files[0]}", f"+# T2D-MAS draft for {ticket_id}: {FIX_IDEAS[service]}"]
    if inject_secret:  # the report's injection demo: Security-Policy must block this
        lines.append('+PAYMENT_GATEWAY_API_KEY = "AKIAIOSFODNN7EXAMPLE"')
    lines += ["+MAX_RETRIES = 3", "+BACKOFF_SECONDS = (0.2, 0.5, 1.0)"]
    tests = [f"tests/{service.replace('-', '_')}/test_{ticket_id.lower().replace('-', '_')}_regression.py",
             f"tests/{service.replace('-', '_')}/test_{service.split('-')[0]}_load.py"]
    return {"branch": f"t2d/{ticket_id.lower()}-{service}", "title": f"Fix {service}: {FIX_IDEAS[service]}",
            "summary": FIX_IDEAS[service], "files_touched": files, "tests_added": tests,
            "diff_text": "\n".join(lines), "additions": additions, "deletions": deletions}


def test_catalog(service: str, seed: int, size: int = 3400) -> list[dict[str, Any]]:
    """The project's test suite with each test's history, used to choose what to run first."""
    generator = rng("tests", service, seed)
    catalog = []
    for index in range(size):
        area = SERVICES[index % len(SERVICES)]
        catalog.append({"test_id": f"T{index:04d}", "area": area,
                        "duration_s": round(generator.uniform(0.5, 9.0), 2),
                        "failure_history": round(generator.random() ** 3, 3),
                        "proximity": 1.0 if area == service else round(generator.random() * 0.4, 2),
                        "recently_failed": generator.random() < 0.03})
    return catalog


def run_ci(selected: list[dict[str, Any]], seed: int, service: str) -> dict[str, Any]:
    """Run the chosen tests (simulated). Returns which positions failed, for NAPFD."""
    generator = rng("ci", seed, service)
    failed_positions = [position for position, test in enumerate(selected, start=1)
                        if test["area"] == service and generator.random() < 0.06]
    flaky = sum(generator.random() < 0.01 for _ in selected)
    return {"failed_positions": failed_positions, "flaky_retried": flaky,
            "duration_minutes": round(sum(test["duration_s"] for test in selected) / 60, 2)}


def deployment_history(service: str, seed: int) -> dict[str, Any]:
    generator = rng("deploy-history", service, seed)
    deployments = generator.randrange(30, 60)
    rollbacks = generator.randrange(1, 4)
    return {"deployments_last_90_days": deployments, "rollbacks": rollbacks,
            "rollback_rate": round(rollbacks / deployments, 3)}


def run_canary(service: str, seed: int, percent: int, regression: bool) -> dict[str, Any]:
    """Watch a canary for 30 simulated minutes; roll back automatically on an SLO breach."""
    metrics = post_release_metrics(service, seed + percent, regression)
    slo = DEFAULT_SLO_BASELINES[service]
    breach = metrics["latency_p95_ms"] > slo["latency_p95_ms"]["slo"] or metrics["error_rate"] > slo["error_rate"]["slo"]
    return {"percent": percent, "observe_minutes": 30, "slo_breach": breach, "metrics": metrics,
            "status": "rolled_back" if breach else "passed"}

