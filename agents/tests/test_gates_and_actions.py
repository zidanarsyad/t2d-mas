"""Gates that stop the run, and the two irreversible actions they protect."""
import asyncio

import pytest

from agents import tools
from agents.audit import MemoryAuditSink
from agents.orchestrator import T2DOrchestrator
from agents.pipeline import Conflict
from agents.repository import GuardViolation, MemoryRepository
from agents.tests.helpers import fixed_triage, interpret_as_given, walk


def advance_until_paused(pipeline, ticket_id):
    async def run():
        snapshot = pipeline.snapshot(ticket_id)
        while snapshot["status"] == "running":
            snapshot = await pipeline.advance(ticket_id)
        return snapshot
    return asyncio.run(run())


def test_a_leaked_secret_blocks_the_draft_until_it_is_redrafted(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("Low", 0.82), interpret=interpret_as_given)
    ticket_id = asyncio.run(pipeline.create_ticket(feedback_id="FB-031",
                                                   options={"inject_test_secret": True}))["ticket_id"]
    blocked = advance_until_paused(pipeline, ticket_id)
    assert blocked["waiting_for"] == "secret_scan"
    assert blocked["pending_gate"]["allowed_intents"] == ["reject", "request_changes"]
    draft = blocked["agent_outputs"]["implementation"]
    assert not draft["security_precheck"]["passed"] and "<REDACTED SECRET>" in draft["draft_pr"]["diff_preview"]
    assert "AKIAIOSFODNN7EXAMPLE" not in str(pipeline.audit.events)
    assert not pipeline.repository.code_changes  # a draft with a secret is never stored

    with pytest.raises(Conflict):
        asyncio.run(pipeline.review(ticket_id, "reviewer", True, "accept", "Ship it anyway"))
    asyncio.run(pipeline.review(ticket_id, "reviewer", False, "request_changes", "Remove the key"))
    resumed = advance_until_paused(pipeline, ticket_id)
    assert resumed["agent_outputs"]["implementation"]["security_precheck"]["passed"]
    assert resumed["waiting_for"] == "pr_merge"


def test_a_risky_release_needs_a_person_before_the_canary(make_pipeline, monkeypatch):
    monkeypatch.setattr(tools, "deployment_history",
                        lambda _service, _seed: {"deployments_last_90_days": 10, "rollbacks": 4, "rollback_rate": 0.4})
    pipeline = make_pipeline(classify=fixed_triage("Low", 0.82), interpret=interpret_as_given)
    ticket_id = asyncio.run(pipeline.create_ticket(feedback_id="FB-031"))["ticket_id"]

    final, gates = asyncio.run(walk(pipeline, ticket_id))
    assert gates == ["pr_merge", "canary_review", "release_signoff"]
    deployment = final["agent_outputs"]["deployment"]
    assert deployment["risk_score"] > 0.30 and deployment["canary"]["status"] == "passed"
    assert final["status"] == "completed"


def test_a_safe_release_starts_the_canary_alone_but_never_the_full_release(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("Low", 0.82), interpret=interpret_as_given)
    ticket_id = asyncio.run(pipeline.create_ticket(feedback_id="FB-060"))["ticket_id"]
    final, gates = asyncio.run(walk(pipeline, ticket_id))
    assert gates == ["pr_merge", "release_signoff"]
    assert final["agent_outputs"]["deployment"]["risk_score"] <= 0.30
    canary = [row for row in pipeline.repository.deployments.values() if row["environment"] == "canary"]
    assert canary and canary[0]["human_approved"] is False  # allowed: a 5% canary of a low-risk change


def test_irreversible_actions_need_a_recorded_approval():
    orchestrator = T2DOrchestrator(MemoryAuditSink())
    orchestrator.start("T-9")
    ran = []
    assert orchestrator.execute_irreversible("T-9", "merge", lambda: ran.append("merge")) is False
    assert orchestrator.execute_irreversible("T-9", "full_deploy", lambda: ran.append("deploy")) is False
    assert ran == []
    blocked = [event for event in orchestrator.audit_sink.events if event.decision == "blocked"]
    assert [event.action for event in blocked] == ["merge", "full_deploy"]


def test_the_memory_store_refuses_the_same_writes_as_the_database_triggers():
    repository = MemoryRepository(MemoryAuditSink())
    repository.save_code_change({"change_id": "C-1", "ticket_id": "T-1", "repository": "demo"})
    with pytest.raises(GuardViolation):
        repository.mark_merged("C-1", "someone", human_approved=False)
    with pytest.raises(GuardViolation):
        repository.save_deployment({"deployment_id": "D-1", "change_id": "C-1", "ticket_id": "T-1",
                                    "environment": "production", "strategy": "full", "status": "deployed"})
