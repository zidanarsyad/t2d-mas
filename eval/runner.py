"""Run a seeded four-arm T2D-MAS classroom simulation and write all artifacts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import random
import re
import statistics
import time
import tracemalloc
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC

from agents.bus import ACLMessage, serialize_acl_message
from agents.mobility import AgentBundle, serialize_bundle
from eval.metrics import average_precision, dora_metrics, macro_f1, napfd, recall_at_k
from eval.report import build_report
from eval.security_injection import run_security_injection
from eval.stats import cliffs_delta, friedman_nemenyi, holm_bonferroni, wilcoxon_signed_rank
from triage.gate import evaluate_gate

ARMS = ("A0", "A1", "A2", "A3")
SEVERITIES = ("Low", "Medium", "High", "Critical")
STAGES = ("triage", "assignment", "investigation", "implementation", "qa", "deployment")
ARM_DESCRIPTIONS = {
    "A0": "Rule-based, single process", "A1": "Single agent",
    "A2": "Multi-agent with static agents", "A3": "Multi-agent with mobile agents",
}


def make_tickets(seed: int, count: int) -> list[dict[str, Any]]:
    """Create one reproducible ticket set shared unchanged by all four arms."""
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        severity = SEVERITIES[index % len(SEVERITIES)]
        parent_index = index - 4 if index >= 4 and index % 7 == 0 else None
        duplicate_of = f"TCK-{parent_index:05d}" if parent_index is not None else ""
        keyword = {"Low": "minor cosmetic", "Medium": "feature regression",
                   "High": "service outage", "Critical": "critical data loss"}[severity]
        if parent_index is not None:
            # Synthetic duplicate examples reuse issue content, without exposing the label in text.
            parent = rows[parent_index]
            title = f"Follow-up: {parent['title']}"
            body = f"{parent['body']} Additional reproduction details from report {index}."
            component = parent["component"]
        else:
            title = f"{keyword} in component-{index % 8}"
            body = (f"{title}. Reproduction details for build {1 + index % 13}. "
                    f"Impact score {rng.randrange(1, 100)}.")
            component = f"component-{index % 8}"
        created_at = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=index)).isoformat()
        rows.append({"ticket_id": f"TCK-{index:05d}", "title": title, "body": body,
                     "component": component, "severity": severity,
                     "created_at": created_at, "duplicate_of": duplicate_of,
                     "is_fault": int(severity in ("High", "Critical"))})
    return rows


def _prediction_model(tickets: list[dict[str, Any]], seed: int):
    """Fit TF-IDF + Platt-calibrated LinearSVC on chronological training rows."""
    split = max(20, int(len(tickets) * 0.70))
    train = tickets[:split]
    model = CalibratedClassifierCV(
        estimator=make_pipeline(TfidfVectorizer(ngram_range=(1, 2), max_features=5000),
                                LinearSVC(random_state=seed)),
        method="sigmoid", cv=3,
    )
    model.fit([row["title"] + " " + row["body"] for row in train],
              [row["severity"] for row in train])
    texts = [row["title"] + " " + row["body"] for row in tickets]
    probabilities = model.predict_proba(texts)
    labels = list(model.classes_)
    predictions = []
    for values in probabilities:
        probs = {label: float(values[labels.index(label)]) for label in SEVERITIES}
        predictions.append((max(SEVERITIES, key=probs.__getitem__), probs))
    return predictions, split


def _network_event(arm: str, ticket: dict[str, Any], stage: str, ordinal: int) -> int:
    """Count ACL bytes with the same compact serializer used by RedisStreamBus."""
    message = ACLMessage(
        performative="inform", correlation_id=ticket["ticket_id"],
        content={"stage": stage, "ordinal": ordinal, "ticket_id": ticket["ticket_id"]},
        policy_context={"arm": arm, "tau": 0.70, "risk_max": 0.60},
        sender=f"{arm}-agent", receiver=[f"{arm}-next"],
        message_id=f"{ticket['ticket_id']}-{stage}-{ordinal}",
    )
    return len(serialize_acl_message(message))


def _mobile_event(ticket: dict[str, Any]) -> int:
    """Count a representative MobileAgentRuntime bundle and aggregate-only return."""
    bundle = AgentBundle(
        bundle_id=f"bundle-{ticket['ticket_id']}", agent_id="A3-Scout",
        code_b64="c2NvdXQtY291cnNlLWRlbW8=",
        state={"ticket_id": ticket["ticket_id"], "aggregate_only": True},
        signature="ed25519:" + "A" * 88,
    )
    sent = len(serialize_bundle(bundle))
    returned = len(b'{"request_count":12,"service":"component"}')
    return sent + returned


def _rank_prior_tickets(tickets: list[dict[str, Any]], index: int, arm: str,
                        seed: int) -> list[str]:
    """Rank earlier tickets from visible text/features only, never from duplicate labels."""
    if index == 0:
        return []
    query = tickets[index]
    query_title = set(re.findall(r"[a-z0-9]+", query["title"].lower()))
    query_text = set(re.findall(r"[a-z0-9]+", (query["title"] + " " + query["body"]).lower()))
    scored = []
    for candidate in tickets[:index]:
        if arm == "A0":
            left, right = query_title, set(re.findall(r"[a-z0-9]+", candidate["title"].lower()))
        else:
            left = query_text
            right = set(re.findall(r"[a-z0-9]+", (candidate["title"] + " " + candidate["body"]).lower()))
        union = left | right
        score = len(left & right) / len(union) if union else 0.0
        if arm in {"A2", "A3"} and query["component"] == candidate["component"]:
            score += 0.02
        # Small, seeded arm-specific noise represents differences in retrieval consistency.
        jitter_seed = f"{seed}:{arm}:{query['ticket_id']}:{candidate['ticket_id']}"
        jitter = random.Random(jitter_seed).uniform(-0.01, 0.01) if arm in {"A1", "A2", "A3"} else 0.0
        scored.append((candidate["ticket_id"], score + jitter))
    return [ticket_id for ticket_id, _score in sorted(scored, key=lambda item: (-item[1], item[0]))]


def _stage_work(arm: str, ticket: dict[str, Any], stage: str) -> None:
    """Small deterministic CPU workload stands in for course-demo orchestration."""
    payload = (ticket["title"] + ticket["body"] + stage).encode("utf-8")
    rounds = {"A0": 1, "A1": 2, "A2": 3, "A3": 4}[arm]
    value = payload
    for _ in range(rounds):
        value = hashlib.sha256(value).digest()


def run_arm(seed: int, arm: str, tickets: list[dict[str, Any]],
            predictions: list[tuple[str, dict[str, float]]], split: int):
    """Run one arm and collect per-ticket, per-stage measured and estimated resources."""
    stage_rows, ticket_rows = [], []
    rng = random.Random(seed * 100 + ARMS.index(arm))
    order_rng = random.Random(seed * 1000 + ARMS.index(arm))
    if arm == "A0":
        ordered_indices = list(range(len(tickets)))
    else:
        noise_scale = {"A1": 0.18, "A2": 0.09, "A3": 0.04}[arm]
        scored = [(index, predictions[index][1]["High"] + predictions[index][1]["Critical"]
                   + order_rng.uniform(-noise_scale, noise_scale)) for index in range(len(tickets))]
        ordered_indices = [index for index, _ in sorted(scored, key=lambda pair: (-pair[1], pair[0]))]
    rank_by_index = {ticket_index: rank for rank, ticket_index in enumerate(ordered_indices, start=1)}
    all_fault_ranks = [rank_by_index[index] for index, ticket in enumerate(tickets) if ticket["is_fault"]]
    total_faults = max(1, sum(row["is_fault"] for row in tickets))
    napfd_score = napfd(all_fault_ranks, len(tickets), total_faults)
    tracemalloc.start()
    for index, ticket in enumerate(tickets):
        predicted_class, probabilities = predictions[index]
        confidence = probabilities[predicted_class]
        gate = evaluate_gate(probabilities, tau=0.70, risk_max=0.60,
                             predicted_class=predicted_class)
        human_approved = bool((ticket["severity"] == "Critical" and rng.random() < 0.8)
                              or (ticket["severity"] != "Critical" and rng.random() < 0.1))
        full_requested = bool(arm == "A3" and gate.autonomous and rng.random() < 0.3)
        # Hard safety invariant: no full deployment executes unless a human approved it.
        full_executed = full_requested and human_approved
        bytes_total = messages = tokens_est = cpu_total = wall_total = 0.0
        ticket_peak = 0
        for stage in STAGES:
            message_count = {"A0": 0, "A1": 1, "A2": 2, "A3": 2}[arm]
            if arm == "A3" and stage == "investigation":
                message_count += 1
            network_bytes = sum(_network_event(arm, ticket, stage, i) for i in range(message_count))
            if arm == "A3" and stage == "investigation":
                network_bytes += _mobile_event(ticket)
            before_wall, before_cpu = time.perf_counter(), time.process_time()
            tracemalloc.reset_peak()
            _stage_work(arm, ticket, stage)
            wall_s = time.perf_counter() - before_wall
            cpu_s = time.process_time() - before_cpu
            _, peak = tracemalloc.get_traced_memory()
            ticket_peak = max(ticket_peak, peak)
            # This is an estimate only; no LLM API is called in the repeatable course harness.
            tokens = 0 if arm == "A0" else (len(ticket["title"] + ticket["body"]) + 3) // 4
            bytes_total += network_bytes
            messages += message_count
            tokens_est += tokens
            cpu_total += cpu_s
            wall_total += wall_s
            stage_rows.append({
                "seed": seed, "arm": arm, "ticket_id": ticket["ticket_id"], "stage": stage,
                "wall_time_s": wall_s, "network_bytes": network_bytes,
                "messages": message_count, "llm_tokens_estimated": tokens,
                "cpu_seconds": cpu_s, "peak_memory_bytes": peak,
                "bytes_source": "ACL serializer; MobileAgentRuntime bundle serializer for A3",
                "token_source": "estimated_characters_div_4" if arm != "A0" else "none",
                "dataset_version": "synthetic-eval-v1",
            })
        # Use a deterministic test ordering proxy so NAPFD is comparable across arms.
        rank = rank_by_index[index]
        relevant = [ticket["duplicate_of"]] if ticket["duplicate_of"] else []
        ranked = _rank_prior_tickets(tickets, index, arm, seed)
        deployable = predicted_class != "Critical" or human_approved
        success = bool(deployable and (not ticket["is_fault"] or rng.random() < 0.88))
        rollback = deployable and not success
        ticket_rows.append({
            "seed": seed, "arm": arm, "arm_description": ARM_DESCRIPTIONS[arm],
            "ticket_id": ticket["ticket_id"], "severity_actual": ticket["severity"],
            "severity_predicted": predicted_class, "severity_confidence": confidence,
            "critical_probability": probabilities["Critical"], "severity_eval_split": index >= split,
            "duplicate_of": ticket["duplicate_of"], "duplicate_eval_query": bool(relevant),
            "recall_at_5": recall_at_k(relevant, ranked, 5) if relevant else "",
            "average_precision": average_precision(relevant, ranked) if relevant else "",
            "napfd": napfd_score,
            "total_wall_time_s": wall_total, "network_bytes": int(bytes_total),
            "messages": messages, "llm_tokens_estimated": tokens_est,
            "cpu_seconds": cpu_total, "peak_memory_bytes": ticket_peak,
            "human_approved": human_approved, "full_deploy_requested": full_requested,
            "full_deploy_executed": full_executed,
            "deployment_success": success, "rollback": rollback,
            "lead_time_hours_simulated": max(0.05, wall_total * 100 + (index % 11)),
            "recovery_hours_simulated": (0.5 + (index % 6) * 0.25) if rollback else 0.0,
            "reworked": int((index + ARMS.index(arm)) % 10 == 0),
            "fault_rank": rank if ticket["is_fault"] else "",
            "dataset_version": "synthetic-eval-v1",
        })
    tracemalloc.stop()
    return ticket_rows, stage_rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write UTF-8 CSV with stable headers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["dataset_version"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_statistics(rows: list[dict[str, Any]], out_dir: Path, alpha: float) -> None:
    """Calculate paired seed summaries, Friedman/Nemenyi, effects, and Holm corrections."""
    metrics = ("total_wall_time_s", "network_bytes", "cpu_seconds", "rollback")
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["arm"], row["seed"]), []).append(row)
    values = {metric: {arm: [] for arm in ARMS} for metric in metrics}
    for metric in metrics:
        for arm in ARMS:
            for seed in sorted({row["seed"] for row in rows}):
                values[metric][arm].append(statistics.mean(float(r[metric]) for r in grouped[(arm, seed)]))
    tests, raw_indices = [], []
    for metric in metrics:
        for left_index, left in enumerate(ARMS):
            for right in ARMS[left_index + 1:]:
                result = wilcoxon_signed_rank(values[metric][left], values[metric][right])
                raw_indices.append(len(tests))
                tests.append({"metric": metric, "test": "wilcoxon_signed_rank", "arm_a": left,
                              "arm_b": right, **result,
                              "cliffs_delta": cliffs_delta(values[metric][left], values[metric][right])})
        omnibus, pairs = friedman_nemenyi(values[metric])
        tests.append({"metric": metric, "test": "friedman", "arm_a": "all", "arm_b": "all",
                      **omnibus, "cliffs_delta": ""})
        for pair in pairs:
            tests.append({"metric": metric, "test": "nemenyi", **pair,
                          "statistic": pair["q"], "cliffs_delta": ""})
    corrected = holm_bonferroni([float(tests[index]["p_value"]) for index in raw_indices])
    for index, adjusted in zip(raw_indices, corrected, strict=True):
        tests[index]["p_holm"] = adjusted
        tests[index]["significant_holm"] = adjusted < alpha
    for row in tests:
        row["dataset_version"] = "synthetic-eval-v1"
    _write_csv(out_dir / "statistical_tests.csv", tests)


def run(config_path: Path, output_root: Path) -> Path:
    """Run configured seeds/arms and write one complete timestamped result bundle."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out_dir = output_root / stamp
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    metadata = {"created_at_utc": stamp, "dataset_version": config["dataset_version"],
                "python": platform.python_version(),
                "platform": platform.platform(), "randomness": "fixed seeds from config",
                "measurement_note": config["notes"]}
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    all_tickets, all_stages = [], []
    for seed in config["seeds"]:
        tickets = make_tickets(int(seed), int(config["tickets_per_seed"]))
        predictions, split = _prediction_model(tickets, int(seed))
        for arm in ARMS:
            arm_tickets, arm_stages = run_arm(int(seed), arm, tickets, predictions, split)
            all_tickets.extend(arm_tickets)
            all_stages.extend(arm_stages)
    _write_csv(out_dir / "per_ticket.csv", all_tickets)
    _write_csv(out_dir / "per_stage.csv", all_stages)
    injection_rows, injection_summary = run_security_injection(seed=int(config["master_seed"]))
    _write_csv(out_dir / "security_injection_cases.csv", injection_rows)
    _write_csv(out_dir / "security_injection_summary.csv", [injection_summary])
    if injection_summary["passed_to_next_stage"] != 0:
        raise RuntimeError("Synthetic policy injection target failed: policy violations escaped")
    summary = []
    for arm in ARMS:
        arm_rows = [row for row in all_tickets if row["arm"] == arm]
        eval_rows = [row for row in arm_rows if row["severity_eval_split"]]
        dora = dora_metrics(
            # Each independent seed represents a separate 30-day synthetic observation window.
            successful_deployments=sum(row["deployment_success"] for row in arm_rows),
            total_days=30.0 * len(config["seeds"]),
            lead_times_hours=[row["lead_time_hours_simulated"] for row in arm_rows],
            recovery_times_hours=[row["recovery_hours_simulated"] for row in arm_rows if row["rollback"]],
            failed_deployments=sum(row["rollback"] for row in arm_rows), total_deployments=len(arm_rows),
            reworked_changes=sum(row["reworked"] for row in arm_rows), total_changes=len(arm_rows))
        summary.append({
            "arm": arm, "arm_description": ARM_DESCRIPTIONS[arm],
            "dataset_version": config["dataset_version"], "ticket_count": len(arm_rows),
            "wall_time_mean_s": statistics.mean(r["total_wall_time_s"] for r in arm_rows),
            "wall_time_median_s": statistics.median(r["total_wall_time_s"] for r in arm_rows),
            "wall_time_p95_s": float(np.percentile([r["total_wall_time_s"] for r in arm_rows], 95)),
            "network_bytes_mean": statistics.mean(r["network_bytes"] for r in arm_rows),
            "messages_mean": statistics.mean(r["messages"] for r in arm_rows),
            "llm_tokens_estimated_mean": statistics.mean(r["llm_tokens_estimated"] for r in arm_rows),
            "cpu_seconds_mean": statistics.mean(r["cpu_seconds"] for r in arm_rows),
            "peak_memory_bytes_max": max(r["peak_memory_bytes"] for r in arm_rows),
            "macro_f1_severity": macro_f1([r["severity_actual"] for r in eval_rows],
                                           [r["severity_predicted"] for r in eval_rows], SEVERITIES),
            "mean_recall_at_5": statistics.mean(float(r["recall_at_5"]) for r in arm_rows if r["duplicate_eval_query"]),
            "mean_average_precision": statistics.mean(float(r["average_precision"]) for r in arm_rows if r["duplicate_eval_query"]),
            "napfd_mean": statistics.mean(r["napfd"] for r in arm_rows),
            "rollback_rate": statistics.mean(float(r["rollback"]) for r in arm_rows),
            "full_deploy_executions": sum(r["full_deploy_executed"] for r in arm_rows),
            "full_deploy_without_approval": sum(r["full_deploy_executed"] and not r["human_approved"] for r in arm_rows),
            **dora,
        })
    _write_csv(out_dir / "summary.csv", summary)
    _write_statistics(all_tickets, out_dir, float(config["alpha"]))
    build_report(out_dir)
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("eval/config.json"))
    parser.add_argument("--output-root", type=Path, default=Path("results"))
    args = parser.parse_args()
    print(f"Evaluation complete: {run(args.config, args.output_root).resolve()}")


if __name__ == "__main__":
    main()
