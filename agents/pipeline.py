"""The ticket pipeline: runs the nine agents in order, applies their gates, keeps the record.

There is no web code here; agents/routes_tickets.py exposes it over HTTP. Each
ticket is a plain dict record (inputs and agent outputs) plus a TicketRun in the
orchestrator (stage, pauses, approvals). Every agent output, gate decision and
message is written to the append-only audit log.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from agents import feedback_samples, tools
from agents.audit import AuditEvent
from agents.brokers import SQUADS, BrokerAssign, BrokerTriage
from agents.events import EventHub
from agents.messaging import MessageService
from agents.orchestrator import STAGES, Gate, PipelinePaused, T2DOrchestrator
from agents.policy import Policy
from agents.scouts import ScoutFeedback, ScoutMonitor
from agents.severity_triage import classify_ticket_with_llm, interpret_review_feedback
from agents.similarity import TfidfCosine
from agents.stage_agent import StageContext
from agents.workers import WorkerDeploy, WorkerImpl, WorkerInvestigate, WorkerPlan, WorkerQA

STAGE_AGENT_IDS = {"intake": "Scout-Feedback", "triage": "Broker-Triage", "assignment": "Broker-Assign",
                   "investigation": "Worker-Investigate", "planning": "Worker-Plan", "implementation": "Worker-Impl",
                   "qa": "Worker-QA", "deployment": "Worker-Deploy", "monitoring": "Scout-Monitor"}
NEXT_AGENT = {"intake": "Broker-Triage", "triage": "Broker-Assign", "investigation": "Worker-Plan",
              "planning": "Worker-Impl", "implementation": "Worker-QA", "qa": "Worker-Deploy",
              "deployment": "Scout-Monitor", "monitoring": "Broker-Triage"}  # monitoring closes the loop
GATE_STAGE = {"duplicate_review": "triage", "autonomy_gate": "triage", "secret_scan": "implementation",
              "pr_merge": "qa", "canary_review": "deployment", "release_signoff": "deployment"}
GATE_NEXT_STAGE = {"autonomy_gate": "assignment", "secret_scan": "qa", "pr_merge": "deployment",
                   "canary_review": "deployment", "release_signoff": "monitoring"}
CLOSED = {"completed", "rejected", "duplicate"}


class NotFound(LookupError):
    """No ticket with that id."""


class Conflict(RuntimeError):
    """The ticket is not in a state that allows this action."""


class InvalidInput(ValueError):
    """The request is missing something a person must provide."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Node:
    """One data node the Scout-Log agent can visit (a container, or an in-process app in local mode)."""
    node_id: str
    service: str
    url: str
    transport: Any = None
    kind: str = "http"


@dataclass
class Deps:
    audit: Any
    repository: Any
    bus: Any
    events: EventHub
    mobile: Any
    nodes: list[Node]
    policy: Policy
    classify: Callable[..., Any] = classify_ticket_with_llm
    interpret: Callable[..., Any] = interpret_review_feedback
    new_ticket_id: Callable[[], str] = field(default=lambda: f"TEST-{uuid4().hex[:8].upper()}")


class TicketPipeline:
    def __init__(self, deps: Deps) -> None:
        self.deps = deps
        self.audit, self.repository, self.events = deps.audit, deps.repository, deps.events
        self.mobile, self.nodes, self.policy = deps.mobile, deps.nodes, deps.policy
        self.classify, self.interpret = deps.classify, deps.interpret
        self.messages = MessageService(deps.bus, deps.audit, deps.events)
        self.orchestrator = T2DOrchestrator(deps.audit)
        self.duplicates = TfidfCosine(feedback_samples.background_texts())
        self.records: dict[str, dict[str, Any]] = {}
        self._order: dict[str, int] = {}  # ticket id -> creation sequence number
        self._locks: dict[str, asyncio.Lock] = {}
        self.agents = {"intake": ScoutFeedback(), "triage": BrokerTriage(), "assignment": BrokerAssign(),
                       "investigation": WorkerInvestigate(), "planning": WorkerPlan(), "implementation": WorkerImpl(),
                       "qa": WorkerQA(), "deployment": WorkerDeploy(), "monitoring": ScoutMonitor()}

    # ---- services the agents use through ctx.deps -----------------------------------------
    async def emit(self, event_type: str, **fields: Any) -> None:
        await self.events.publish({"type": event_type, "occurred_at": now(), **fields})

    def squad_load(self, exclude_ticket: str) -> dict[str, int]:
        load = {worker: 0 for worker in SQUADS}
        for ticket_id, record in self.records.items():
            if ticket_id != exclude_ticket and record.get("assignee") in load and self._status(ticket_id) not in CLOSED:
                load[record["assignee"]] += 1
        return load

    def reported_before(self, other_id: str, ticket_id: str) -> bool:
        """True if `other_id` came in before `ticket_id` (tickets from earlier runs always did).

        Creation order is used instead of timestamps, which can tie on fast machines.
        """
        if other_id == ticket_id:
            return False
        order = self._order
        return other_id not in order or order[other_id] < order.get(ticket_id, len(order))

    def tickets_from_feedback(self, feedback_id: str | None, exclude_ticket: str) -> list[str]:
        if not feedback_id:
            return []
        return [ticket_id for ticket_id, record in self.records.items()
                if record.get("feedback_id") == feedback_id and ticket_id != exclude_ticket]

    # ---- public API --------------------------------------------------------------------------
    async def create_ticket(self, body: str | None = None, title: str | None = None, channel: str = "manual",
                            feedback_id: str | None = None, options: dict[str, Any] | None = None,
                            metadata: dict[str, Any] | None = None, parent_ticket_id: str | None = None) -> dict[str, Any]:
        sample = feedback_samples.get(feedback_id) if feedback_id else None
        if sample and not body:  # starting from an inbox message
            body, title = sample.text, title or sample.title
            channel, metadata = sample.channel, {**sample.metadata, "author": sample.author, **(metadata or {})}
        body = (body or "").strip()
        if len(body) < 10:
            raise InvalidInput("Describe the problem in at least 10 characters.")
        if title is not None and title.strip() and len(title.strip()) < 3:
            raise InvalidInput("A title needs at least 3 characters (or leave it empty).")
        ticket_id = self.deps.new_ticket_id()
        record = {"ticket_id": ticket_id, "created_at": now(), "channel": channel, "feedback_id": feedback_id,
                  "title": None, "body": None, "severity": "Unknown", "severity_confidence": None,
                  "severity_rationale": None, "language": None, "component": None, "app_version": None,
                  "platform": None, "title_derived": False, "duplicate_of": None, "duplicate_override": None,
                  "assignee": None, "sla_due": None, "parent_ticket_id": parent_ticket_id,
                  "follow_up_ticket_ids": [], "options": {"inject_test_secret": False, "simulate_regression": False,
                                                          **(options or {})},
                  "metadata": metadata or {}, "reviews": [], "review_requested_at": None, "irreversible_actions": [],
                  "_raw": {"title": (title or "").strip(), "body": body}, "_outputs": {}, "_revisions": {},
                  "_guidance": {}}
        self.records[ticket_id] = record
        self._order[ticket_id] = len(self._order)
        self.orchestrator.start(ticket_id)
        output = await self._run_stage(record, "intake")
        await self._handoff(record, "intake", output)
        await self.emit("ticket.started", ticket_id=ticket_id, stage="intake", title=record["title"],
                        severity=record["severity"], channel=channel, parent_ticket_id=parent_ticket_id)
        return self.snapshot(ticket_id)

    async def advance(self, ticket_id: str) -> dict[str, Any]:
        async with self._lock(ticket_id):
            record = self._record(ticket_id)
            status = self._status(ticket_id)
            if status == "waiting_for_review":
                return self.snapshot(ticket_id)
            if status in CLOSED:
                raise Conflict(f"This ticket is {status}.")
            run = self.orchestrator.runs[ticket_id]
            stage = run.stage.value
            output = record["_outputs"].get(stage)
            fresh = output is None
            if fresh:
                output = await self._run_stage(record, stage)
            if stage == "triage" and output["duplicate"]["band"] == "auto_link" and not record["duplicate_override"]:
                # A near-identical report: link it and stop; the original keeps the investigation.
                best = output["duplicate"]["best_match"]
                await self._close_as_duplicate(record, best["ticket_id"], best["cosine"], automatic=True)
                return self.snapshot(ticket_id)
            if fresh:
                await self._handoff(record, stage, output)
            try:
                run = self.orchestrator.advance(ticket_id, gates=self._gates(output))
            except PipelinePaused:
                await self._paused(record)
                return self.snapshot(ticket_id)
            await self._advanced(record)
            return self.snapshot(ticket_id)

    async def review(self, ticket_id: str, approver: str, approved: bool, intent: str | None,
                     reason: str) -> dict[str, Any]:
        from agents.reviews import handle_review  # keeps the review rules in their own module

        async with self._lock(ticket_id):
            return await handle_review(self, ticket_id, approver, approved, intent, reason)

    async def follow_up_from_anomaly(self, anomaly: dict[str, Any]) -> dict[str, Any]:
        """Scout-Monitor turns a monitoring anomaly into a new ticket (the feedback loop)."""
        existing = self.tickets_from_feedback(anomaly["anomaly_id"], "")
        if existing:
            return self.snapshot(existing[0])
        return await self.create_ticket(
            body=_alert_text(anomaly), title=f"Monitoring alert: {anomaly['service']} {_metric_name(anomaly['metric'])}",
            channel="monitoring", feedback_id=anomaly["anomaly_id"],
            metadata={"anomaly": anomaly, "author": "Scout-Monitor"})

    def snapshot(self, ticket_id: str) -> dict[str, Any]:
        record, run = self._record(ticket_id), self.orchestrator.runs[ticket_id]
        status = self._status(ticket_id)
        done = {item["from"] for item in run.history}
        if run.completed and status == "completed":
            done.add(run.stage.value)
        entered = {"intake": run.started_at, **{item["to"]: item["at"] for item in run.history}}
        current_index = STAGES.index(run.stage)
        stages = []
        for index, stage in enumerate(STAGES):
            if stage.value in done:
                state = "completed"
            elif status == "duplicate" and index > current_index:
                state = "skipped"
            elif index == current_index:
                state = {"rejected": "rejected", "duplicate": "completed"}.get(status, "current")
            else:
                state = "upcoming"
            stages.append({"name": stage.value, "agent": self._agent_for(record, stage.value), "status": state,
                           "entered_at": entered.get(stage.value)})
        public = {key: value for key, value in record.items() if not key.startswith("_")}
        return {**public, "agent_outputs": record["_outputs"], "status": status, "current_stage": run.stage.value,
                "waiting_for": run.waiting_for, "stages": stages,
                "pending_gate": self._pending_gate(record) if status == "waiting_for_review" else None}

    def list_tickets(self) -> list[dict[str, Any]]:
        return [self.snapshot(ticket_id) for ticket_id in reversed(self.records)]

    # ---- helpers -------------------------------------------------------------------------------
    def _record(self, ticket_id: str) -> dict[str, Any]:
        if ticket_id not in self.records:
            raise NotFound("Ticket not found.")
        return self.records[ticket_id]

    def _lock(self, ticket_id: str) -> asyncio.Lock:
        self._record(ticket_id)
        return self._locks.setdefault(ticket_id, asyncio.Lock())

    def _status(self, ticket_id: str) -> str:
        run = self.orchestrator.runs[ticket_id]
        if run.waiting_for == "rejected":
            return "rejected"
        if run.closed_reason == "duplicate":
            return "duplicate"
        if run.waiting_for:
            return "waiting_for_review"
        return "completed" if run.completed else "running"

    def _agent_for(self, record: dict[str, Any], stage: str) -> str:
        if stage == "investigation" and record.get("assignee"):
            return record["assignee"]
        return STAGE_AGENT_IDS[stage]

    @staticmethod
    def _gates(output: dict[str, Any]) -> list[Gate]:
        return [Gate(item["gate"], item["autonomous"], item["reason"]) for item in output.get("decisions", [])]

    def context(self, record: dict[str, Any], stage: str) -> StageContext:
        return StageContext(ticket=record, outputs=record["_outputs"], policy=self.policy,
                            seed=tools.stable_seed(record["ticket_id"]), deps=self,
                            guidance=record["_guidance"].get(stage), revision=record["_revisions"].get(stage, 0))

    async def _run_stage(self, record: dict[str, Any], stage: str) -> dict[str, Any]:
        """Run one agent, store its output, audit it and its gate decisions, update the record."""
        ticket_id = record["ticket_id"]
        await self.emit("stage.started", ticket_id=ticket_id, stage=stage, agent=self._agent_for(record, stage))
        output = await self.agents[stage].run(self.context(record, stage))
        record["_outputs"][stage] = output
        self.audit.append(AuditEvent(actor_id=output["agent"], action="agent_output", decision="completed",
                                     correlation_id=ticket_id, ticket_id=ticket_id,
                                     details={"stage": stage, "execution_mode": output["execution_mode"],
                                              "output": output}))
        self._apply_to_record(record, stage, output)
        for item in output.get("decisions", []):
            await self._audit_gate(record, stage, item)
        if stage == "monitoring" and output["anomalies"] and not record.get("parent_ticket_id"):
            follow_up = await self.create_ticket(
                body=_alert_text({**output["anomalies"][0], "start_minute": 0, "end_minute": 30}),
                title=f"Regression after {ticket_id}", channel="monitoring", feedback_id=f"MON-{ticket_id}",
                parent_ticket_id=ticket_id, metadata={"author": "Scout-Monitor"})
            output["follow_up_ticket_id"] = follow_up["ticket_id"]
            record["follow_up_ticket_ids"].append(follow_up["ticket_id"])
            await self.emit("ticket.follow_up", parent_ticket_id=ticket_id, ticket_id=follow_up["ticket_id"],
                            anomaly_id=f"MON-{ticket_id}")
        await self.emit("stage.completed", ticket_id=ticket_id, stage=stage, agent=output["agent"],
                        summary=output["summary"], execution_mode=output["execution_mode"],
                        decisions=output.get("decisions", []))
        return output

    def _apply_to_record(self, record: dict[str, Any], stage: str, output: dict[str, Any]) -> None:
        if stage == "intake":
            record.pop("_raw", None)
            record.update({key: output[key] for key in ("title", "body", "language", "component", "app_version",
                                                         "platform", "title_derived")})
        elif stage == "triage":
            record.update(severity=output["severity"], severity_confidence=output["confidence"],
                          severity_rationale=output["rationale"])
        elif stage == "assignment":
            record.update(assignee=output["winner"], sla_due=output["sla_due"])

    async def _audit_gate(self, record: dict[str, Any], stage: str, item: dict[str, Any]) -> None:
        details = {"stage": stage, "gate": item["gate"], "reason": item["reason"], "inputs": item["inputs"],
                   "policy_id": item["policy_id"]}
        triage = record["_outputs"].get("triage", {})
        if item["gate"] == "autonomy_gate":  # what the triage decision was based on
            details.update(severity=record["severity"], risk=item["inputs"].get("risk"),
                           tau=item["inputs"].get("tau"), risk_max=item["inputs"].get("risk_max"),
                           rate_limited=bool(triage.get("rate_limited")), provider=triage.get("provider"),
                           fallback_reason=triage.get("fallback_reason"))
        self.audit.append(AuditEvent(actor_id="Security-Policy", action="policy_gate",
                                     decision="autonomous" if item["autonomous"] else "escalated",
                                     correlation_id=record["ticket_id"], ticket_id=record["ticket_id"],
                                     confidence=item["inputs"].get("confidence"), details=details))
        await self.emit("gate.evaluated", ticket_id=record["ticket_id"], stage=stage, gate=item["gate"],
                        autonomous=item["autonomous"], reason=item["reason"], inputs=item["inputs"])

    async def _handoff(self, record: dict[str, Any], stage: str, output: dict[str, Any]) -> None:
        """Send the stage result as an ACL "inform" to whoever acts next."""
        blocked = any(not item["autonomous"] for item in output.get("decisions", []))
        if blocked:
            target = "Human-Reviewer"
        elif stage == "assignment":
            target = output["winner"]
        else:
            target = NEXT_AGENT[stage]
        await self.messages.inform(record["ticket_id"], output["agent"], [target],
                                   {"stage": stage, "summary": output["summary"], "output": output},
                                   {"tau": self.policy.tau, "risk_max": self.policy.risk_max})

    async def _paused(self, record: dict[str, Any]) -> None:
        run = self.orchestrator.runs[record["ticket_id"]]
        record["review_requested_at"] = now()
        pending = run.approval_queue[-1] if run.approval_queue else {"checkpoint": run.waiting_for, "reason": ""}
        await self.emit("approval.requested", ticket_id=record["ticket_id"], checkpoint=pending["checkpoint"],
                        reason=pending["reason"])

    async def _advanced(self, record: dict[str, Any]) -> None:
        run = self.orchestrator.runs[record["ticket_id"]]
        await self.emit("pipeline.advanced", ticket_id=record["ticket_id"], stage=run.stage.value)
        if run.completed:
            self.repository.update_ticket(record["ticket_id"], status="completed")
            await self.emit("pipeline.completed", ticket_id=record["ticket_id"])

    async def _close_as_duplicate(self, record: dict[str, Any], parent_id: str, cosine: float,
                                  automatic: bool) -> None:
        root, seen = parent_id, {record["ticket_id"]}
        while self.records.get(root, {}).get("duplicate_of") and root not in seen:  # link to the original
            seen.add(root)
            root = self.records[root]["duplicate_of"]
        record["duplicate_of"] = root
        self.repository.update_ticket(record["ticket_id"], status="duplicate", duplicate_of=root)
        self.orchestrator.close(record["ticket_id"], "duplicate")
        await self.messages.inform(record["ticket_id"], "Broker-Triage", ["Scout-Feedback"],
                                   {"stage": "triage", "decision": "linked_duplicate", "parent_ticket_id": root,
                                    "cosine": cosine, "automatic": automatic,
                                    "summary": f"Linked to {root}; the original ticket keeps the investigation."})
        await self.emit("duplicate.linked", ticket_id=record["ticket_id"], parent_ticket_id=root,
                        cosine=cosine, automatic=automatic)

    def _pending_gate(self, record: dict[str, Any]) -> dict[str, Any]:
        from agents.reviews import allowed_intents

        run = self.orchestrator.runs[record["ticket_id"]]
        gate = run.waiting_for
        stage = GATE_STAGE.get(gate, run.stage.value)
        output = record["_outputs"].get(stage, {})
        item = next((entry for entry in output.get("decisions", []) if entry["gate"] == gate), {})
        label = next((entry["label"] for entry in self.policy.gates() if entry["gate"] == gate), "Human review")
        pending = run.approval_queue[0] if run.approval_queue else {}
        return {"gate": gate, "stage": stage, "reason": pending.get("reason") or item.get("reason"),
                "question": label, "allowed_intents": sorted(allowed_intents(record, gate)),
                "evidence": {"summary": output.get("summary"), **item.get("inputs", {})}}


def _metric_name(metric: str) -> str:
    """Plain words for a metric id in ticket titles: latency_p95_ms -> p95 latency."""
    return {"latency_p95_ms": "p95 latency", "error_rate": "error rate"}.get(metric, metric.replace("_", " "))


def _metric_value(metric: str, value: Any) -> str:
    """2348.0 -> "2,348 ms" for latency, 0.064 -> "6.4%" for an error rate."""
    if not isinstance(value, (int, float)):
        return str(value)
    if "latency" in metric:
        return f"{value:,.0f} ms"
    if metric == "error_rate":
        return f"{value:.1%}"
    return f"{value:g}"


def _alert_text(anomaly: dict[str, Any]) -> str:
    metric = anomaly["metric"]
    value = anomaly.get("peak_value", anomaly.get("value"))
    return (f"Automatic alert from Scout-Monitor: {anomaly['service']} {_metric_name(metric)} reached "
            f"{_metric_value(metric, value)} (baseline {_metric_value(metric, anomaly['baseline_mean'])}, "
            f"z = {anomaly['z']}) between minute {anomaly.get('start_minute', 0)} and "
            f"{anomaly.get('end_minute', anomaly.get('peak_minute', 0))}. Customers may see slow or failed requests.")
