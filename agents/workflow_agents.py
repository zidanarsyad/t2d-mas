"""Deterministic specialist behaviors for the interactive course prototype.

These agents make the nine-stage run inspectable without claiming access to a
repository, production telemetry, a CI runner, or a deployment environment.
"""
from __future__ import annotations

from typing import Any

from agents.broker_assign import Proposal


STAGE_AGENT_IDS = {
    "intake": "Scout-Feedback",
    "triage": "Broker-Triage",
    "assignment": "Broker-Assign",
    "investigation": "Worker-Investigate",
    "planning": "Worker-Plan",
    "implementation": "Worker-Impl",
    "qa": "Worker-QA",
    "deployment": "Worker-Deploy",
    "monitoring": "Scout-Monitor",
}

HANDOFF_TARGETS = {
    "intake": "Broker-Triage",
    "triage": "Security-Policy",
    "assignment": "Worker-Investigate",
    "investigation": "Worker-Plan",
    "planning": "Worker-Impl",
    "implementation": "Worker-QA",
    "qa": "Human-Reviewer",
    "deployment": "Human-Reviewer",
    "monitoring": "Orchestrator",
}


def assignment_proposals(record: dict[str, Any]) -> list[Proposal]:
    """Create normalized, inspectable worker bids for the Contract Net demo."""
    profiles = [
        ("Worker-Investigate", 0.84, 0.26, 0.29),
        ("Worker-Plan", 0.71, 0.48, 0.31),
        ("Worker-Impl", 0.79, 0.31, 0.38),
    ]
    text = f"{record.get('title', '')} {record.get('body', '')}".lower()
    if any(cue in text for cue in ("code", "patch", "implementation", "fix")):
        profiles = [(worker, min(1.0, skill + (0.12 if worker == "Worker-Impl" else 0.0)), load, cost)
                    for worker, skill, load, cost in profiles]
    return [Proposal(worker, skill, load, cost) for worker, skill, load, cost in profiles]


def prototype_stage_output(stage: str, record: dict[str, Any]) -> dict[str, Any]:
    """Return a concrete prototype result, explicitly labeling simulated work."""
    body = str(record.get("body", ""))
    text = f"{record.get('title', '')} {body}".lower()
    if stage == "investigation":
        clues = []
        if any(word in text for word in ("checkout", "payment", "card", "purchase")):
            clues.append({"hypothesis": "checkout or payment dependency", "evidence": "ticket wording", "confidence": 0.42})
        if any(word in text for word in ("login", "sign in", "authentication", "session")):
            clues.append({"hypothesis": "identity or session dependency", "evidence": "ticket wording", "confidence": 0.38})
        if any(word in text for word in ("slow", "latency", "timeout", "unavailable", "outage")):
            clues.append({"hypothesis": "service latency or availability", "evidence": "ticket wording", "confidence": 0.35})
        if not clues:
            clues.append({"hypothesis": "component not yet localized", "evidence": "no observability evidence connected", "confidence": 0.2})
        return {"status": "hypotheses_only", "method": "local keyword heuristic", "ranked_hypotheses": clues,
                "telemetry_collected": False, "root_cause_confirmed": False}
    if stage == "planning":
        return {"status": "plan_drafted", "subtasks": [
                    "Reproduce the reported behavior and capture the failing path",
                    "Inspect the highest-ranked hypothesis with service evidence",
                    "Prepare a scoped change and acceptance checks"],
                "acceptance_criteria": ["The reported scenario is reproducible", "A regression check covers the scenario",
                                        "No unrelated behavior regresses"],
                "effort_estimate": "not estimated without repository and sprint data"}
    if stage == "implementation":
        return {"status": "change_request_drafted", "code_change_generated": False,
                "draft_action": "Inspect repository context and prepare a change after the plan is reviewed",
                "repository_access": False, "requires_llm_or_coding_tool": True}
    if stage == "qa":
        return {"status": "not_run_no_patch", "tests_executed": 0,
                "recommended_checks": ["Run the reproduction case", "Run focused regression tests", "Run the project test suite"],
                "pass_fail": "undetermined", "ci_runner_connected": False}
    if stage == "deployment":
        return {"status": "canary_proposal_only", "rollout_percentage": 5,
                "canary_result": "not_observed", "full_release_executed": False,
                "production_deployment_connected": False, "checkpoint": "release_signoff"}
    if stage == "monitoring":
        return {"status": "awaiting_telemetry", "telemetry_source": None,
                "slo_check": "not_run", "follow_up_ticket_created": False,
                "feedback_loop_target": "Broker-Triage"}
    raise ValueError(f"No prototype behavior is defined for stage {stage!r}")
