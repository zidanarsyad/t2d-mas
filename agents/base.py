"""Canonical five-part agent interface and audited action boundary."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents.audit import AuditEvent, AuditSink
from agents.logging_config import correlation_id_var
from agents.pii import mask_value
from agents.security_policy import GateDecision, evaluate_gate


class Mobility(str, Enum):
    STATIC = "STATIC"
    MOBILE = "MOBILE"


@dataclass
class AutonomyPolicy:
    tau: float = 0.70
    risk_max: float = 0.60


@dataclass
class AgentContext:
    correlation_id: str
    ticket_id: str | None = None
    human_approved: bool = False
    probability: float = 1.0
    risk_class: str = "Low"
    metadata: dict[str, Any] = field(default_factory=dict)


class Agent(ABC):
    """Base class with perceive, remember, reason, act, and report hooks."""

    def __init__(self, agent_id: str, role: str, mobility: Mobility,
                 autonomy_policy: AutonomyPolicy, audit_sink: AuditSink) -> None:
        self.agent_id = agent_id
        self.role = role
        self.mobility = mobility
        self.autonomy_policy = autonomy_policy
        self.audit_sink = audit_sink
        self.memory: dict[str, Any] = {}

    @abstractmethod
    def perceive(self, observation: Any) -> Any:
        """Convert an external observation into an agent-specific input."""

    def remember(self, key: str, value: Any) -> None:
        """Store a small piece of state for later reasoning."""
        self.memory[key] = value

    @abstractmethod
    def reason(self, perceived: Any) -> Any:
        """Produce a plan or proposed action."""

    @abstractmethod
    def act(self, proposal: Any, context: AgentContext) -> Any:
        """Execute an action. Irreversible actions must recheck human approval."""

    @abstractmethod
    def report(self, result: Any) -> Any:
        """Format a compact, auditable result."""

    def execute(self, observation: Any, context: AgentContext) -> tuple[Any, GateDecision]:
        """Run the canonical loop and record both allowed and escalated actions."""
        token = correlation_id_var.set(context.correlation_id)
        try:
            perceived = self.perceive(observation)
            self.remember(context.correlation_id, perceived)
            proposal = self.reason(perceived)
            audit_proposal = mask_value(proposal)
            decision = evaluate_gate(context.probability, context.risk_class,
                                     self.autonomy_policy.tau, self.autonomy_policy.risk_max)
            # Merge and production deploy remain approval-only even when the generic gate passes.
            irreversible = isinstance(proposal, dict) and proposal.get("action") in {"merge", "full_deploy"}
            allowed = decision.autonomous and (not irreversible or context.human_approved)
            if not allowed and context.human_approved:
                # The gate escalates high risk; the recorded human decision resolves that escalation.
                allowed = True
            if allowed:
                # Write-ahead audit means an unavailable audit store fails closed.
                self.audit_sink.append(AuditEvent(
                    actor_id=self.agent_id,
                    action=str(proposal.get("action", "agent_action")) if isinstance(proposal, dict) else "agent_action",
                    decision="authorized_to_execute",
                    correlation_id=context.correlation_id,
                    ticket_id=context.ticket_id,
                    confidence=context.probability,
                    human_approved=context.human_approved,
                    details={"role": self.role, "mobility": self.mobility.value,
                             "gate_reason": decision.reason, "risk": decision.risk,
                             "proposal": audit_proposal},
                ))
                result = self.act(proposal, context)
                status = "executed"
            else:
                result = {"status": "approval_required", "proposal": proposal}
                status = "escalated"
            self.audit_sink.append(AuditEvent(
                actor_id=self.agent_id,
                action=str(proposal.get("action", "agent_action")) if isinstance(proposal, dict) else "agent_action",
                decision=status,
                correlation_id=context.correlation_id,
                ticket_id=context.ticket_id,
                confidence=context.probability,
                human_approved=context.human_approved,
                details={"role": self.role, "mobility": self.mobility.value,
                         "gate_reason": decision.reason, "risk": decision.risk,
                         "proposal": audit_proposal, "output": mask_value(result)},
            ))
            reported = self.report(result)
            self.audit_sink.append(AuditEvent(
                actor_id=self.agent_id, action="agent_report", decision="reported",
                correlation_id=context.correlation_id, ticket_id=context.ticket_id,
                confidence=context.probability, human_approved=context.human_approved,
                details={"role": self.role, "output": mask_value(reported)},
            ))
            return reported, decision
        finally:
            correlation_id_var.reset(token)
