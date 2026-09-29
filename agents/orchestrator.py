"""Nine-stage ticket pipeline with explicit, blocking human checkpoints."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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
# Checkpoints reflect BAB 5: severity sign-off, human PR review/merge, and release sign-off.
CHECKPOINTS = {Stage.TRIAGE: "severity_signoff", Stage.QA: "pr_merge", Stage.DEPLOYMENT: "release_signoff"}


@dataclass
class TicketRun:
    ticket_id: str
    stage: Stage = Stage.INTAKE
    waiting_for: str | None = None
    approval_queue: list[dict[str, Any]] = field(default_factory=list)
    human_approved: bool = False
    history: list[dict[str, Any]] = field(default_factory=list)


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

    def advance(self, ticket_id: str, decision: GateDecision | None = None,
                human_approved: bool = False, correlation_id: str | None = None) -> TicketRun:
        """Advance one stage, pausing at escalations and all three named checkpoints."""
        run = self.runs[ticket_id]
        correlation_id = correlation_id or ticket_id
        correlation_id_var.set(correlation_id)
        if run.waiting_for:
            raise PipelinePaused(f"ticket {ticket_id} waits for {run.waiting_for}")
        if decision is not None and not decision.autonomous and not human_approved:
            self._enqueue(run, "autonomy_gate", decision.reason, correlation_id)
            raise PipelinePaused(f"ticket {ticket_id} escalated by autonomy gate")
        checkpoint = CHECKPOINTS.get(run.stage)
        if checkpoint and not human_approved:
            self._enqueue(run, checkpoint, "human_checkpoint", correlation_id)
            raise PipelinePaused(f"ticket {ticket_id} waits for {checkpoint}")
        previous = run.stage
        index = STAGES.index(previous)
        if index == len(STAGES) - 1:
            self._log(run, "pipeline_complete", "complete", {})
            return run
        run.stage = STAGES[index + 1]
        run.human_approved = human_approved
        run.history.append({"from": previous.value, "to": run.stage.value,
                            "human_approved": human_approved})
        self._log(run, "advance_stage", "advanced", {"from": previous.value,
                  "to": run.stage.value, "human_approved": human_approved})
        # A successful one-time approval applies to this transition only.
        run.human_approved = False
        return run

    def approve(self, ticket_id: str, approver: str, approved: bool,
                reason: str = "") -> TicketRun:
        run = self.runs[ticket_id]
        if not run.waiting_for:
            raise ValueError("ticket is not waiting for human approval")
        item = run.approval_queue.pop(0)
        self._log(run, "human_approval", "approved" if approved else "rejected",
                  {"checkpoint": item["checkpoint"], "approver": approver, "reason": reason,
                   "human_approved": approved})
        if not approved:
            run.waiting_for = "rejected"
            raise PipelinePaused(f"ticket {ticket_id} was rejected: {reason}")
        run.waiting_for = None
        run.human_approved = True
        # Human action clears the pause but does not itself perform the stage transition.
        run._approved_checkpoint = item["checkpoint"]  # type: ignore[attr-defined]
        return run

    def resume_approved(self, ticket_id: str) -> TicketRun:
        run = self.runs[ticket_id]
        if not run.human_approved:
            raise PipelinePaused("no approval recorded")
        # Re-enter advance with explicit human flag; this advances only one checkpoint stage.
        return self.advance(ticket_id, human_approved=True)

    def perform_irreversible(self, ticket_id: str, action: str, human_approved: bool,
                             callback: Any | None = None) -> bool:
        """Never invoke merge/full-deploy callbacks without an explicit human flag."""
        if action in {"merge", "full_deploy"} and not human_approved:
            self._log(self.runs[ticket_id], action, "blocked", {"human_approved": False})
            return False
        # Fail closed if the audit store is unavailable: irreversible work starts only after this insert.
        self._log(self.runs[ticket_id], action, "authorized_to_execute",
                  {"human_approved": human_approved})
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
