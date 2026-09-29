from agents.audit import MemoryAuditSink
from agents.orchestrator import PipelinePaused, T2DOrchestrator
from agents.security_policy import evaluate_gate


def test_escalation_blocks_progress_until_human_approval():
    sink = MemoryAuditSink()
    pipeline = T2DOrchestrator(sink)
    run = pipeline.start("T-1")
    pipeline.advance("T-1")
    try:
        pipeline.advance("T-1", decision=evaluate_gate(0.88, "Critical"))
    except PipelinePaused:
        pass
    assert run.stage.value == "triage"
    assert run.waiting_for == "autonomy_gate"
    pipeline.approve("T-1", "reviewer", True, "confirmed")
    pipeline.resume_approved("T-1")
    assert run.stage.value == "assignment"
    assert any(event.action == "approval_requested" for event in sink.events)


def test_merge_and_full_deploy_require_explicit_human_flag():
    pipeline = T2DOrchestrator(MemoryAuditSink())
    pipeline.start("T-2")
    executions = []
    callback = lambda: executions.append("ran")
    assert pipeline.perform_irreversible("T-2", "full_deploy", False, callback) is False
    assert pipeline.perform_irreversible("T-2", "merge", False, callback) is False
    assert executions == []
    assert pipeline.perform_irreversible("T-2", "full_deploy", True, callback) is True
    assert executions == ["ran"]
