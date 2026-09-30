import asyncio

from agents import app as api
from agents.audit import MemoryAuditSink
from agents.app import ManualReview, ManualTicket
from agents.orchestrator import T2DOrchestrator


def test_manual_pipeline_emits_all_agent_outputs_and_handoffs(monkeypatch):
    audit = MemoryAuditSink()

    class Bus:
        def __init__(self):
            self.count = 0

        async def publish(self, _message):
            self.count += 1
            return f"{self.count}-0"

    async def classifier(_text):
        return {"severity": "High", "confidence": 0.68, "matched_cues": ["outage"],
                "rationale": "Impact language matched: outage.", "agent": "rule-based triage",
                "provider": "rules"}

    async def no_event(_event):
        return None

    monkeypatch.setattr(api.app.state, "audit", audit, raising=False)
    monkeypatch.setattr(api.app.state, "pipeline", T2DOrchestrator(audit), raising=False)
    monkeypatch.setattr(api.app.state, "manual_ticket_records", {}, raising=False)
    bus = Bus()
    monkeypatch.setattr(api.app.state, "bus", bus, raising=False)
    monkeypatch.setattr(api, "_save_ticket_record", lambda *_args: None)
    monkeypatch.setattr(api, "classify_ticket_with_llm", classifier)
    monkeypatch.setattr(api.event_hub, "publish", no_event)

    async def run():
        record = await api.start_manual_ticket(ManualTicket(
            title="Checkout outage", body="Customers cannot complete checkout during a sale."
        ))
        ticket_id = record["ticket_id"]
        await api.advance_manual_ticket(ticket_id)  # intake -> triage
        paused = await api.advance_manual_ticket(ticket_id)
        assert paused["waiting_for"] == "autonomy_gate"

        resumed = await api.review_manual_ticket(ticket_id, ManualReview(
            approver="reviewer", approved=True, reason="Accept the high impact classification"
        ))
        assert resumed["current_stage"] == "assignment"

        for _ in range(5):  # assignment -> investigation -> planning -> implementation -> QA review
            result = await api.advance_manual_ticket(ticket_id)
        assert result["waiting_for"] == "pr_merge"
        result = await api.review_manual_ticket(ticket_id, ManualReview(
            approver="reviewer", approved=True, reason="Accept the prototype QA report"
        ))
        assert result["current_stage"] == "deployment"

        result = await api.advance_manual_ticket(ticket_id)
        assert result["waiting_for"] == "release_signoff"
        result = await api.review_manual_ticket(ticket_id, ManualReview(
            approver="release-manager", approved=True, reason="Accept the simulated canary proposal"
        ))
        assert result["current_stage"] == "monitoring"
        return await api.advance_manual_ticket(ticket_id)

    final = asyncio.run(run())
    assert final["status"] == "completed"
    output_events = [event for event in audit.events if event.action == "agent_output"]
    assert {event.details["stage"] for event in output_events} == {
        "intake", "triage", "assignment", "investigation", "planning", "implementation", "qa", "deployment", "monitoring"
    }
    stage_outputs = {event.details["stage"]: event.details["output"] for event in output_events}
    assert stage_outputs["assignment"]["winner"]
    assert stage_outputs["implementation"]["code_change_generated"] is False
    assert stage_outputs["qa"]["tests_executed"] == 0
    assert stage_outputs["deployment"]["full_release_executed"] is False
    assert bus.count >= 15  # startup, policy, Contract Net, stage handoffs, and reviews
    assert sum(event.action == "agent_message" for event in audit.events) == bus.count * 2


def test_rejected_review_stops_pipeline_and_masks_note(monkeypatch):
    audit = MemoryAuditSink()

    class Bus:
        async def publish(self, _message):
            return "reject-test-1"

    async def classifier(_text):
        return {"severity": "High", "confidence": 0.68, "matched_cues": ["outage"],
                "rationale": "Impact language matched: outage.", "agent": "rule-based triage",
                "provider": "rules"}

    async def no_event(_event):
        return None

    monkeypatch.setattr(api.app.state, "audit", audit, raising=False)
    monkeypatch.setattr(api.app.state, "pipeline", T2DOrchestrator(audit), raising=False)
    monkeypatch.setattr(api.app.state, "manual_ticket_records", {}, raising=False)
    monkeypatch.setattr(api.app.state, "bus", Bus(), raising=False)
    monkeypatch.setattr(api, "_save_ticket_record", lambda *_args: None)
    monkeypatch.setattr(api, "classify_ticket_with_llm", classifier)
    monkeypatch.setattr(api.event_hub, "publish", no_event)

    async def run():
        record = await api.start_manual_ticket(ManualTicket(
            title="Checkout outage", body="Customers cannot complete checkout during a sale."
        ))
        await api.advance_manual_ticket(record["ticket_id"])
        await api.advance_manual_ticket(record["ticket_id"])
        return record["ticket_id"], await api.review_manual_ticket(record["ticket_id"], ManualReview(
            approver="reviewer", approved=False, reason="Reject; contact alice@example.com"
        ))

    ticket_id, rejected = asyncio.run(run())
    assert rejected["status"] == "rejected"
    assert rejected["current_stage"] == "triage"
    approval = next(event for event in audit.events if event.action == "human_approval")
    assert approval.decision == "rejected"
    assert approval.details["reason"] == "Reject; contact <EMAIL>"
    rejection_message = next(event for event in audit.events
                             if event.action == "agent_message" and event.decision == "publish_authorized"
                             and event.ticket_id == ticket_id and event.actor_id == "reviewer")
    assert rejection_message.details["content"]["note"] == "Reject; contact <EMAIL>"


def test_request_changes_revises_triage_and_appends_interpretation_to_audit(monkeypatch):
    audit = MemoryAuditSink()

    class Bus:
        async def publish(self, _message):
            return "review-revision-1"

    async def classifier(_text, review_feedback=None):
        severity = "High" if review_feedback else "Medium"
        result = {"severity": severity, "confidence": 0.65, "matched_cues": ["outage"],
                  "rationale": "Reviewer correction considered." if review_feedback else "Initial classification.",
                  "agent": "Broker-Triage (OpenRouter)" if review_feedback else "rule-based triage",
                  "provider": "openrouter" if review_feedback else "rules",
                  "model": "qwen/qwen3.8-27b:free" if review_feedback else None}
        if review_feedback:
            result["review_interpretation"] = {
                "summary": "Treat this as a high-impact outage.",
                "requested_changes": ["Reclassify severity as High"], "constraints": [],
                "evidence": ["All customers are affected"], "needs_clarification": False,
                "interpreter": "openrouter", "model": "qwen/qwen3.8-27b:free"}
        return result

    async def no_event(_event):
        return None

    monkeypatch.setattr(api.app.state, "audit", audit, raising=False)
    monkeypatch.setattr(api.app.state, "pipeline", T2DOrchestrator(audit), raising=False)
    monkeypatch.setattr(api.app.state, "manual_ticket_records", {}, raising=False)
    monkeypatch.setattr(api.app.state, "bus", Bus(), raising=False)
    monkeypatch.setattr(api, "_save_ticket_record", lambda *_args: None)
    monkeypatch.setattr(api, "_update_ticket_severity", lambda *_args: None)
    monkeypatch.setattr(api, "classify_ticket_with_llm", classifier)
    monkeypatch.setattr(api.event_hub, "publish", no_event)

    async def run():
        record = await api.start_manual_ticket(ManualTicket(
            title="Checkout outage", body="All customers are unable to finish checkout."
        ))
        ticket_id = record["ticket_id"]
        await api.advance_manual_ticket(ticket_id)
        await api.advance_manual_ticket(ticket_id)
        return await api.review_manual_ticket(ticket_id, ManualReview(
            approver="reviewer", approved=False, intent="request_changes",
            reason="All customers are affected, so classify this as High."
        ))

    revised = asyncio.run(run())
    assert revised["status"] == "running"
    assert revised["current_stage"] == "triage"
    assert revised["severity"] == "High"
    review = revised["reviews"][-1]
    assert review["intent"] == "request_changes"
    assert review["interpretation"]["requested_changes"] == ["Reclassify severity as High"]
    history_event = next(event for event in audit.events
                         if event.action == "review_revision_requested")
    assert history_event.details["reason"] == "All customers are affected, so classify this as High."
    assert history_event.details["interpretation"] == review["interpretation"]
    revised_triage = next(event for event in audit.events
                          if event.action == "agent_output" and event.details.get("stage") == "triage"
                          and event.details["output"].get("revision") == 1)
    assert revised_triage.details["output"]["severity"] == "High"
