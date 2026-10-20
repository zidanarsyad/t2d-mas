"""One place for every threshold the agents and the dashboard use.

The defaults mirror the report: tau 0.70 and R_max 0.60 for the autonomy gate,
duplicate bands at 0.85 / 0.70, a 5% canary that may run on its own only when the
release risk score is at most 0.30, and the mobile-agent rule L_node > (A + R) * 3.
At startup the orchestrator may load an approved row from the `policies` table;
otherwise these code defaults apply (GET /policy reports which one is active).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from triage.gate import RISK_BY_CLASS


@dataclass(frozen=True)
class Policy:
    policy_id: str = "default-v1"
    source: str = "code_defaults"
    # Autonomy gate: act alone only if confidence >= tau AND risk <= risk_max.
    tau: float = 0.70
    risk_max: float = 0.60
    # Duplicate bands (cosine similarity): >= auto_link links, >= review asks a human.
    duplicate_auto_link: float = 0.85
    duplicate_review: float = 0.70
    # Deployment: a small canary may start alone only for low-risk releases.
    canary_percent: int = 5
    canary_risk_max: float = 0.30
    canary_observe_minutes: int = 30
    # Mobile agents: migrate when the node's log volume exceeds (agent + result) * factor.
    migration_factor: float = 3.0
    agent_bundle_mb: float = 12.0
    result_mb: float = 2.0
    # QA test budget and the monitoring anomaly threshold (z-score).
    ci_budget_minutes: int = 8
    anomaly_z: float = 3.0
    sla_hours: dict[str, int] = field(default_factory=lambda: {
        "Critical": 2, "High": 8, "Medium": 72, "Low": 168})

    def rules(self) -> dict[str, Any]:
        """The non-gate thresholds, stored as JSON in the `policies` table."""
        values = asdict(self)
        for key in ("policy_id", "source", "tau", "risk_max"):
            values.pop(key)
        return values

    def gates(self) -> list[dict[str, Any]]:
        """Plain-language gate table for the dashboard and the audit report."""
        return [
            {"gate": "duplicate_review", "label": "Confirm the duplicate", "stage": "triage",
             "agent": "Broker-Triage", "reversible": True,
             "autonomous_when": f"similarity >= {self.duplicate_auto_link:.2f} (link) or "
                                f"< {self.duplicate_review:.2f} (new ticket)",
             "human_when": f"{self.duplicate_review:.2f} <= similarity < {self.duplicate_auto_link:.2f}"},
            {"gate": "autonomy_gate", "label": "Confirm the impact assessment", "stage": "triage",
             "agent": "Broker-Triage", "reversible": True,
             "autonomous_when": f"confidence >= {self.tau:.2f} and risk <= {self.risk_max:.2f}",
             "human_when": "low confidence or high risk (Critical is always high risk)"},
            {"gate": "secret_scan", "label": "Remove a secret from the change", "stage": "implementation",
             "agent": "Security-Policy", "reversible": True,
             "autonomous_when": "no secret found in the draft change",
             "human_when": "a secret is found; it can only be redrafted or stopped"},
            {"gate": "pr_merge", "label": "Review the proposed change", "stage": "qa",
             "agent": "Worker-QA", "reversible": False,
             "autonomous_when": "never", "human_when": "always: merging to main needs a code review"},
            {"gate": "canary_review", "label": f"Approve the {self.canary_percent}% canary",
             "stage": "deployment", "agent": "Worker-Deploy", "reversible": True,
             "autonomous_when": f"release risk score <= {self.canary_risk_max:.2f}",
             "human_when": f"release risk score > {self.canary_risk_max:.2f}"},
            {"gate": "release_signoff", "label": "Approve the full release", "stage": "deployment",
             "agent": "Worker-Deploy", "reversible": False,
             "autonomous_when": "never", "human_when": "always: a full deploy needs a release sign-off"},
        ]

    def to_api(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id, "source": self.source,
            "tau": self.tau, "risk_max": self.risk_max, "risk_by_class": dict(RISK_BY_CLASS),
            "duplicate": {"auto_link": self.duplicate_auto_link, "review": self.duplicate_review},
            "canary": {"percent": self.canary_percent, "risk_max": self.canary_risk_max,
                       "observe_minutes": self.canary_observe_minutes},
            "migration": {"factor": self.migration_factor, "agent_bundle_mb": self.agent_bundle_mb,
                          "result_mb": self.result_mb},
            "ci": {"budget_minutes": self.ci_budget_minutes},
            "monitoring": {"anomaly_z": self.anomaly_z},
            "sla_hours": dict(self.sla_hours),
            "gates": self.gates(),
            "irreversible_actions": ["merge", "full_deploy"],
        }


DEFAULT_POLICY = Policy()


def policy_from_row(row: dict[str, Any] | None) -> Policy:
    """Build a Policy from a `policies` row; unknown or missing rules keep their defaults."""
    if not row:
        return DEFAULT_POLICY
    known = {key: value for key, value in (row.get("rules") or {}).items()
             if key in DEFAULT_POLICY.rules()}
    return replace(DEFAULT_POLICY, policy_id=str(row.get("policy_id", DEFAULT_POLICY.policy_id)),
                   source="database", tau=float(row.get("tau", DEFAULT_POLICY.tau)),
                   risk_max=float(row.get("risk_max", DEFAULT_POLICY.risk_max)), **known)


def duplicate_band(score: float, policy: Policy = DEFAULT_POLICY) -> str:
    """Map a cosine similarity to auto_link, review, or new (report section 6.4.1)."""
    if score >= policy.duplicate_auto_link:
        return "auto_link"
    if score >= policy.duplicate_review:
        return "review"
    return "new"


def canary_autonomous(risk_score: float, policy: Policy = DEFAULT_POLICY) -> bool:
    """A small canary may start without a human only for low-risk releases (report T21)."""
    return risk_score <= policy.canary_risk_max


def sla_due(severity: str, start: datetime, policy: Policy = DEFAULT_POLICY) -> str:
    hours = policy.sla_hours.get(severity, policy.sla_hours["Medium"])
    return (start + timedelta(hours=hours)).isoformat()
