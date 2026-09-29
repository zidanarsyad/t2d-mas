"""Deterministic event trace for the report's BAB 8.5 flash-sale case."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.audit import AuditSink
from agents.orchestrator import PipelinePaused, Stage, T2DOrchestrator
from agents.security_policy import evaluate_gate


@dataclass(frozen=True)
class ScenarioEvent:
    minute: int
    event: str
    agent: str
    result: dict[str, Any]

    @property
    def time_label(self) -> str:
        return f"{self.minute // 60:02d}:{self.minute % 60:02d}"


def run_flash_sale(audit_sink: AuditSink) -> list[ScenarioEvent]:
    """Replay the fixed timeline and enforce the same gates used by the pipeline."""
    pipeline = T2DOrchestrator(audit_sink)
    ticket_id = "TCK-1042"
    run = pipeline.start(ticket_id)
    events = [ScenarioEvent(0, "crash_reports_grouped", "Scout-Feedback",
                            {"ticket_count": 2143, "parent": ticket_id, "duplicates_linked": 2142})]
    run = pipeline.advance(ticket_id)
    events.append(ScenarioEvent(12, "related_ticket_found", "Broker-Triage",
                               {"match_id": "TCK-0987", "cosine": 0.91, "duplicate": False}))
    critical = evaluate_gate(0.88, "Critical", tau=0.70, risk_max=0.60)
    try:
        pipeline.advance(ticket_id, decision=critical)
    except PipelinePaused:
        events.append(ScenarioEvent(20, "severity_escalated", "Broker-Triage",
                                   {"probability": 0.88, "risk": critical.risk, "waiting": run.waiting_for}))
    pipeline.approve(ticket_id, "incident-commander", True, "Confirmed severity Critical")
    pipeline.resume_approved(ticket_id)
    events.append(ScenarioEvent(90, "severity_confirmed", "Approval Inbox", {"severity": "Critical"}))
    events.append(ScenarioEvent(95, "worker_assigned", "Broker-Assign", {"worker": "W2", "utility": 0.69}))
    # Move through assignment, investigation, planning, implementation, and QA.
    for _ in range(4):
        pipeline.advance(ticket_id)
    events.append(ScenarioEvent(100, "mobile_log_analysis_started", "Scout-Log",
                               {"nodes": 6, "local_log_mb_per_node": 1365,
                                "bytes_sent_mb": 72, "bytes_returned_mb": 12,
                                "total_bytes_mb": 84, "elapsed_s": 27,
                                "static_reference_s": 655}))
    events.extend([
        ScenarioEvent(125, "root_cause_ranked", "Worker-Investigate", {"service": "payment-db", "score": 2.60}),
        ScenarioEvent(140, "plan_created", "Worker-Plan", {"subtasks": 3}),
        ScenarioEvent(170, "patch_and_tests_ready", "Worker-Impl", {"draft_pr": True, "new_tests": 2}),
        ScenarioEvent(185, "qa_completed", "Worker-QA", {"tests_selected": 120, "suite_size": 3400,
                                                            "budget_minutes": 8, "napfd": 0.94, "all_passed": True}),
    ])
    # The QA checkpoint is the review/merge gate; human_approved is separately tested at the action boundary.
    try:
        pipeline.advance(ticket_id)
    except PipelinePaused:
        pass
    pipeline.approve(ticket_id, "reviewer", True, "Production code review passed")
    pipeline.perform_irreversible(ticket_id, "merge", human_approved=True)
    pipeline.resume_approved(ticket_id)
    events.append(ScenarioEvent(195, "pr_review_and_merge", "Human", {"merged": True, "human_approved": True}))
    events.append(ScenarioEvent(205, "canary_5_percent", "Worker-Deploy", {"risk_score": 0.28,
                                                                            "slo_breach": False,
                                                                            "observation_minutes": 30}))
    try:
        pipeline.advance(ticket_id)
    except PipelinePaused:
        pass
    pipeline.approve(ticket_id, "release-manager", True, "Full release approved after canary")
    pipeline.perform_irreversible(ticket_id, "full_deploy", human_approved=True)
    pipeline.resume_approved(ticket_id)
    events.append(ScenarioEvent(240, "full_release_signoff", "Human", {"human_approved": True}))
    pipeline.advance(ticket_id)
    events.append(ScenarioEvent(270, "monitoring_and_close", "Scout-Monitor", {"baseline_updated": True,
                                                                                 "ticket_closed": True}))
    return events
