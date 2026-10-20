"""Scout agents: they collect information at the edges of the system.

- Scout-Feedback turns a raw user message into a clean, masked ticket (stage 1).
- Scout-Log is the mobile agent: it travels to the data nodes during investigation.
- Scout-Monitor watches the release and opens a follow-up ticket on an anomaly (stage 9).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents import scout_log_program, tools
from agents.mobility import should_migrate
from agents.pii import mask_with_counts
from agents.security_policy import validate_egress
from agents.stage_agent import StageAgent, StageContext, Step
from agents.text import (derive_title, detect_language, extract_app_version, extract_device_platform,
                         extract_repro_hints, guess_component)

CHANNEL_LABELS = {"app_store_review": "app-store review", "email": "e-mail", "portal_form": "help-portal form",
                  "cs_chat": "customer-service chat", "slack": "Slack escalation", "crash_reporter": "crash report",
                  "monitoring": "monitoring alert", "manual": "manually entered"}
SCOUT_LOG_SOURCE = Path(scout_log_program.__file__).read_text(encoding="utf-8")


class ScoutFeedback(StageAgent):
    stage, agent_id, family, execution_mode = "intake", "Scout-Feedback", "Scout", "live"

    async def perceive(self, ctx: StageContext) -> Step:
        raw = ctx.ticket["_raw"]
        title, title_counts = mask_with_counts(raw.get("title") or "")
        body, body_counts = mask_with_counts(raw["body"])
        counts = {key: title_counts[key] + body_counts[key] for key in body_counts}
        channel = CHANNEL_LABELS.get(ctx.ticket.get("channel", "manual"), "message")
        masked = ", ".join(f"{count} {kind}" for kind, count in counts.items() if count) or "nothing"
        return Step({"title": title, "body": body, "pii": counts},
                     f"Read a {channel} ({len(raw['body'])} characters) and masked personal data: {masked}.")

    async def remember(self, ctx: StageContext, seen: Step) -> Step:
        earlier = ctx.deps.tickets_from_feedback(ctx.ticket.get("feedback_id"), ctx.ticket["ticket_id"])
        note = (f"This message was already captured as {', '.join(earlier)}." if earlier
                else "This message has not been captured before.")
        return Step(earlier, note)

    async def reason(self, ctx: StageContext, seen: Step, memory: Step) -> Step:
        text = f"{seen.data['title']}\n{seen.data['body']}"
        metadata = ctx.ticket.get("metadata") or {}
        component, confidence, cues = guess_component(text)
        device, platform = extract_device_platform(text)
        facts = {
            "title": seen.data["title"] or derive_title(seen.data["body"]),
            "title_derived": not seen.data["title"],
            "language": detect_language(seen.data["body"]),
            "app_version": metadata.get("app_version") or extract_app_version(text),
            "platform": metadata.get("platform") or platform,
            "device": metadata.get("device") or device,
            "component": component, "component_confidence": confidence, "component_cues": cues,
            "reproduction_hints": extract_repro_hints(seen.data["body"]),
        }
        return Step(facts, f"Language: {facts['language']}. Product area: {component} "
                           f"(cues: {', '.join(cues) or 'none'}). App version: {facts['app_version'] or 'not stated'}.")

    async def act(self, ctx: StageContext, seen: Step, memory: Step, plan: Step) -> Step:
        ctx.use_tool("blackboard.save_ticket", simulated=False, detail="tickets table")
        ctx.deps.repository.save_ticket({
            "ticket_id": ctx.ticket["ticket_id"], "source": ctx.ticket.get("channel", "manual"),
            "title": plan.data["title"], "body": seen.data["body"], "component": plan.data["component"],
            "created_at": ctx.ticket["created_at"], "status": "running", "language": plan.data["language"],
            "app_version": plan.data["app_version"], "platform": plan.data["platform"],
            "parent_ticket_id": ctx.ticket.get("parent_ticket_id")})
        return Step(None, "Saved the masked, normalized ticket to the shared blackboard.")

    def report(self, ctx, seen, memory, plan, result) -> dict[str, Any]:
        facts = plan.data
        return {**facts, "body": seen.data["body"], "source": ctx.ticket.get("channel", "manual"),
                "feedback_id": ctx.ticket.get("feedback_id"), "pii_masked": seen.data["pii"],
                "description_characters": len(seen.data["body"]), "already_captured_as": memory.data,
                "summary": f"Turned a {CHANNEL_LABELS.get(ctx.ticket.get('channel'), 'message')} into the ticket "
                           f"\"{facts['title']}\" ({facts['component']}, {facts['language']})."}


class ScoutLog:
    """The mobile agent. It visits each data node and returns only aggregate numbers.

    For each node it applies the report's rule: ship the analysis code when the
    node's log volume L exceeds (A + R) * k; otherwise ask the node's own exporter.
    """

    agent_id, family, mobility = "Scout-Log", "Scout", "MOBILE"

    async def visit(self, ctx: StageContext, node: Any, component: str) -> dict[str, Any]:
        import httpx

        policy = ctx.policy
        visit: dict[str, Any] = {"node_id": node.node_id, "node": node.node_id, "service": node.service,
                                 "transport": node.kind}
        try:
            async with httpx.AsyncClient(base_url=node.url, transport=node.transport, timeout=10) as client:
                inventory = (await client.get("/inventory")).json()
                migrate = should_migrate(inventory["log_mb"], policy.agent_bundle_mb, policy.result_mb,
                                         policy.migration_factor)
                visit["migration_rule"] = {"log_mb": inventory["log_mb"], "agent_mb": policy.agent_bundle_mb,
                                           "result_mb": policy.result_mb, "factor": policy.migration_factor,
                                           "threshold_mb": (policy.agent_bundle_mb + policy.result_mb)
                                           * policy.migration_factor, "should_migrate": migrate}
                if migrate:
                    receipt = await ctx.deps.mobile.migrate(
                        node.url, self.agent_id, SCOUT_LOG_SOURCE,
                        {"seed": ctx.seed, "component": component, "window_minutes": 30},
                        correlation_id=ctx.ticket["ticket_id"], transport=node.transport)
                    visit.update(mode="mobile_agent", aggregate=receipt["aggregate"],
                                 bytes_sent=receipt["bytes_sent"], bytes_returned=receipt["bytes_returned"])
                else:  # cheaper to use the node's exporter than to ship the agent here
                    request = {"seed": ctx.seed, "component": component}
                    response = await client.post("/aggregates", json=request)
                    response.raise_for_status()
                    aggregate = validate_egress(response.json()["result"])
                    visit.update(mode="node_exporter", aggregate=aggregate,
                                 bytes_sent=len(json.dumps(request)), bytes_returned=len(json.dumps(aggregate)))
                visit["error"] = None
        except Exception as exc:  # one failing node must not stop the investigation
            visit.update(mode="failed", aggregate=None, bytes_sent=0, bytes_returned=0, error=str(exc)[:160])
        visit["log_bytes_kept"] = int(visit.get("migration_rule", {}).get("log_mb", 0) * 1_000_000)
        await ctx.deps.emit("agent.migrated", ticket_id=ctx.ticket["ticket_id"], agent_id=self.agent_id,
                            node_id=node.node_id, node=node.node_id, service=node.service, transport=node.kind,
                            mode=visit["mode"], should_migrate=visit.get("migration_rule", {}).get("should_migrate"),
                            log_bytes=visit["log_bytes_kept"], bytes_sent=visit["bytes_sent"],
                            bytes_returned=visit["bytes_returned"])
        return visit


class ScoutMonitor(StageAgent):
    stage, agent_id, family, mobility = "monitoring", "Scout-Monitor", "Scout", "MOBILE"
    simulation_note = "Post-release telemetry is simulated; no production system is connected."

    async def perceive(self, ctx: StageContext) -> Step:
        deployment = ctx.outputs.get("deployment", {})
        service = ctx.outputs.get("investigation", {}).get("rca", {}).get("top_suspect") or "order-service"
        return Step({"service": service, "release": deployment.get("full_release", {})},
                    f"Watched {service} for 30 minutes after the release.")

    async def remember(self, ctx: StageContext, seen: Step) -> Step:
        baselines = ctx.deps.repository.slo_baselines().get(seen.data["service"]) or \
            tools.DEFAULT_SLO_BASELINES[seen.data["service"]]
        return Step(baselines, f"Loaded the SLO baseline for {seen.data['service']} "
                               f"(p95 ≤ {baselines['latency_p95_ms']['slo']} ms, errors ≤ "
                               f"{baselines['error_rate']['slo']:.0%}).")

    async def reason(self, ctx: StageContext, seen: Step, memory: Step) -> Step:
        service = seen.data["service"]
        regression = bool(ctx.ticket.get("options", {}).get("simulate_regression"))
        ctx.use_tool("observability.post_release_metrics", simulated=True, detail=service)
        metrics = tools.post_release_metrics(service, ctx.seed, regression)
        signals = []
        for metric, value in metrics.items():
            base = memory.data[metric]
            z = tools.z_score(value, base["mean"], base["std"])
            signals.append({"service": service, "metric": metric, "value": value, "baseline_mean": base["mean"],
                            "baseline_std": round(base["std"], 4), "z": z, "slo": base["slo"],
                            "breach": z >= ctx.policy.anomaly_z or value > base["slo"]})
        anomalies = [signal for signal in signals if signal["breach"]]
        note = (f"Anomaly: {anomalies[0]['metric']} = {anomalies[0]['value']} (z = {anomalies[0]['z']})."
                if anomalies else f"All signals within the SLO (largest z = {max(s['z'] for s in signals)}).")
        return Step({"signals": signals, "anomalies": anomalies}, note)

    async def act(self, ctx: StageContext, seen: Step, memory: Step, plan: Step) -> Step:
        if plan.data["anomalies"]:
            return Step("follow_up", "Asked Scout-Feedback to open a follow-up ticket (the feedback loop).")
        ctx.use_tool("slo_baselines.update", simulated=True, detail=seen.data["service"])
        return Step("closed", "Updated the SLO baseline with the healthy release window and closed the ticket.")

    def report(self, ctx, seen, memory, plan, result) -> dict[str, Any]:
        anomalies = plan.data["anomalies"]
        return {"window_minutes": 30, "services_checked": [seen.data["service"]], "signals": plan.data["signals"],
                "anomalies": anomalies, "follow_up_ticket_id": None,
                "baseline_updated": not anomalies, "ticket_closed": not anomalies,
                "feedback_loop": {"target": "Broker-Triage",
                                  "reason": "anomaly after release" if anomalies else "release healthy"},
                "summary": (f"Release unhealthy: {anomalies[0]['metric']} breached; opening a follow-up ticket."
                            if anomalies else "Release healthy for 30 minutes; baseline updated and ticket closed.")}
