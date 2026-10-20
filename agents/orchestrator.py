"""Nine-stage ticket pipeline: a small state machine with blocking human gates.

Each stage's agent reports its gate decisions (for example "autonomy_gate:
escalate"). The orchestrator stops at the first gate that is not autonomous and
waits for a human. Merging (after QA) and the full release (after deployment)
always need a human, even if an agent forgot to ask: the orchestrator adds those
two gates itself.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from agents.audit import AuditEvent, AuditSink
from agents.logging_config import correlation_id_var
from agents.security_policy import GateDecision

logger = logging.getLogger(__name__)


class Stage(str, Enum):
    INTAKE = "intake"
    TRIAGE = "triage"
    ASSIGNMENT = "assignment"
    INVESTIGATION = "investigation"
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    QA = "qa"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"


STAGES = list(Stage)
# Gates the orchestrator always enforces, whatever the agents report.
REQUIRED_GATES = {Stage.QA: "pr_merge", Stage.DEPLOYMENT: "release_signoff"}
# Which recorded approval allows which irreversible action.
APPROVAL_FOR_ACTION = {"merge": "pr_merge", "full_deploy": "release_signoff"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Gate:
    """One policy check at a stage; a gate that is not autonomous stops the run for a human."""
    name: str
    autonomous: bool
    reason: str = ""


@dataclass
class TicketRun:
    ticket_id: str
    stage: Stage = Stage.INTAKE
    waiting_for: str | None = None
    approval_queue: list[dict[str, Any]] = field(default_factory=list)
    human_approved: bool = False
    completed: bool = False
    closed_reason: str | None = None          # e.g. "duplicate" when linked to an older ticket
    started_at: str = field(default_factory=_now)
    history: list[dict[str, Any]] = field(default_factory=list)
    pending_gates: list[Gate] = field(default_factory=list)   # the current stage's gates
    cleared: set[str] = field(default_factory=set)            # gates a human approved at this stage
    approvals: dict[str, dict[str, Any]] = field(default_factory=dict)  # gate -> approver and time


class PipelinePaused(RuntimeError):
    """Raised when an approval is required before the pipeline can advance."""


class T2DOrchestrator:
    def __init__(self, audit_sink: AuditSink) -> None:
        self.audit_sink = audit_sink
        self.runs: dict[str, TicketRun] = {}

    def start(self, ticket_id: str) -> TicketRun:
        if ticket_id in self.runs:
            return self.runs[ticket_id]
        run = TicketRun(ticket_id=ticket_id)
        self.runs[ticket_id] = run
        self._log(run, "pipeline_start", "started", {"stage_count": len(STAGES)})
        return run

    def advance(self, ticket_id: str, decision: GateDecision | None = None, *,
                gates: list[Gate] | None = None, correlation_id: str | None = None) -> TicketRun:
        """Move one stage forward, or pause at the first gate that needs a human."""
        run = self.runs[ticket_id]
        correlation_id = correlation_id or ticket_id
        correlation_id_var.set(correlation_id)
        if run.waiting_for:
            raise PipelinePaused(f"ticket {ticket_id} waits for {run.waiting_for}")
        if run.completed:
            return run
        checks = list(gates or [])
        if decision is not None:  # shorthand used by older callers and tests
            checks.insert(0, Gate("autonomy_gate", decision.autonomous, decision.reason))
        required = REQUIRED_GATES.get(run.stage)
        if required and required not in {gate.name for gate in checks}:
            checks.append(Gate(required, False, "human_checkpoint"))
        run.pending_gates = checks
        for gate in checks:
            if not gate.autonomous and gate.name not in run.cleared:
                self._enqueue(run, gate.name, gate.reason or "human_checkpoint", correlation_id)
                raise PipelinePaused(f"ticket {ticket_id} waits for {gate.name}")
        previous = run.stage
        index = STAGES.index(previous)
        approved_here = bool(run.cleared)
        if index == len(STAGES) - 1:
            run.completed = True
            self._log(run, "pipeline_complete", "complete", {})
        else:
            run.stage = STAGES[index + 1]
            run.history.append({"from": previous.value, "to": run.stage.value,
                                "human_approved": approved_here, "at": _now()})
            self._log(run, "advance_stage", "advanced", {"from": previous.value, "to": run.stage.value,
                                                         "human_approved": approved_here})
        # Approvals apply to one stage only.
        run.cleared.clear()
        run.pending_gates = []
        run.human_approved = False
        return run

    def approve(self, ticket_id: str, approver: str, approved: bool, reason: str = "",
                intent: str = "accept", interpretation: dict[str, Any] | None = None,
                next_stage: str | None = None) -> TicketRun:
        run = self.runs[ticket_id]
        if not run.waiting_for:
            raise ValueError("ticket is not waiting for human approval")
        item = run.approval_queue.pop(0)
        self._log(run, "human_approval", "approved" if approved else "rejected",
                  {"checkpoint": item["checkpoint"], "approver": approver, "reason": reason,
                   "intent": intent, "stage": run.stage.value, "next_stage": next_stage,
                   "interpretation": interpretation, "human_approved": approved})
        if not approved:
            run.waiting_for = "rejected"
            raise PipelinePaused(f"ticket {ticket_id} was rejected: {reason}")
        # A human decision clears this gate; the transition itself happens in resume_approved().
        run.waiting_for = None
        run.human_approved = True
        run.cleared.add(item["checkpoint"])
        run.approvals[item["checkpoint"]] = {"approver": approver, "at": _now(), "reason": reason}
        return run

    def resume_approved(self, ticket_id: str) -> TicketRun:
        run = self.runs[ticket_id]
        if not run.human_approved:
            raise PipelinePaused("no approval recorded")
        # Re-check the same gates: the approved one is cleared, a later one may still pause.
        return self.advance(ticket_id, gates=run.pending_gates)

    def request_revision(self, ticket_id: str, approver: str, reason: str,
                         interpretation: dict[str, Any]) -> TicketRun:
        """Clear the current pause without approving it, so the same stage can be revised."""
        run = self.runs[ticket_id]
        if not run.waiting_for:
            raise PipelinePaused("ticket is not waiting for review")
        checkpoint = run.waiting_for
        run.approval_queue.pop(0)
        run.waiting_for = None
        run.human_approved = False
        self._log(run, "review_revision_requested", "revision_requested", {
            "checkpoint": checkpoint, "stage": run.stage.value, "approver": approver, "reason": reason,
            "intent": "request_changes", "interpretation": interpretation})
        return run

    def close(self, ticket_id: str, reason: str) -> TicketRun:
        """End a run early without failing it (for example a ticket linked as a duplicate)."""
        run = self.runs[ticket_id]
        run.completed = True
        run.closed_reason = reason
        self._log(run, "pipeline_closed", reason, {"stage": run.stage.value})
        return run

    def execute_irreversible(self, ticket_id: str, action: str,
                             callback: Callable[[], Any] | None = None) -> bool:
        """Run merge/full_deploy only if the matching gate was approved by a person."""
        approval = self.runs[ticket_id].approvals.get(APPROVAL_FOR_ACTION.get(action, ""))
        return self.perform_irreversible(ticket_id, action, approval is not None, callback)

    def perform_irreversible(self, ticket_id: str, action: str, human_approved: bool,
                             callback: Any | None = None) -> bool:
        """Never invoke merge/full-deploy callbacks without an explicit human flag."""
        if action in APPROVAL_FOR_ACTION and not human_approved:
            self._log(self.runs[ticket_id], action, "blocked", {"human_approved": False})
            return False
        # Fail closed if the audit store is unavailable: irreversible work starts only after this insert.
        self._log(self.runs[ticket_id], action, "authorized_to_execute", {"human_approved": human_approved})
        if callback is not None:
            callback()
        self._log(self.runs[ticket_id], action, "executed", {"human_approved": human_approved})
        return True

    def _enqueue(self, run: TicketRun, checkpoint: str, reason: str, correlation_id: str) -> None:
        run.waiting_for = checkpoint
        run.approval_queue.append({"ticket_id": run.ticket_id, "checkpoint": checkpoint,
                                   "reason": reason, "correlation_id": correlation_id})
        self._log(run, "approval_requested", "escalated", {"checkpoint": checkpoint, "reason": reason})

    def _log(self, run: TicketRun, action: str, decision: str, details: dict[str, Any]) -> None:
        correlation_id = str(details.pop("correlation_id", run.ticket_id))
        logger.info("pipeline event", extra={"correlation_id": correlation_id})
        self.audit_sink.append(AuditEvent(actor_id="orchestrator", action=action,
            decision=decision, correlation_id=correlation_id, ticket_id=run.ticket_id,
            human_approved=bool(details.get("human_approved", False)), details=details))
