import asyncio
import json

import pytest
from fastapi import HTTPException

from agents import app as api
from agents.app import ManualReview, ManualTicket
from agents.audit import MemoryAuditSink
from agents.bus import RedisStreamBus
from agents.orchestrator import T2DOrchestrator


@pytest.fixture
def workspace(monkeypatch):
    audit = MemoryAuditSink()
    monkeypatch.setattr(api.app.state, "audit", audit, raising=False)
    monkeypatch.setattr(api.app.state, "pipeline", T2DOrchestrator(audit), raising=False)
    monkeypatch.setattr(api.app.state, "manual_ticket_records", {}, raising=False)
    monkeypatch.setattr(api, "_save_ticket_record", lambda *_args: None)

    class Bus:
        count = 0

        async def publish(self, _message):
            self.count += 1
            await asyncio.sleep(0)
            return f"{self.count}-0"

    async def classify(_text):
        return {"severity": "Critical", "confidence": 0.84, "matched_cues": ["data corruption"],
                "rationale": "Data corruption affects orders", "agent": "Broker-Triage", "provider": "rules"}

    async def no_event(_event):
        pass

    monkeypatch.setattr(api.app.state, "bus", Bus(), raising=False)
    monkeypatch.setattr(api, "classify_ticket_with_llm", classify)
    monkeypatch.setattr(api.event_hub, "publish", no_event)
    return audit


def test_dashboard_lists_the_same_review_state_and_hides_locks(workspace):
    async def run():
        ticket = await api.start_manual_ticket(ManualTicket(title="Checkout issue", body="Orders have data corruption"))
        await api.advance_manual_ticket(ticket["ticket_id"])
        paused = await api.advance_manual_ticket(ticket["ticket_id"])
        before = len(workspace.events)
        repeated = await api.advance_manual_ticket(ticket["ticket_id"])
        assert len(workspace.events) == before
        assert repeated == paused
        assert paused["review_requested_at"]
        assert api.active_manual_tickets()["items"][0] == paused
        assert not any(key.startswith("_") for key in paused)
        json.dumps(paused)

    asyncio.run(run())


def test_concurrent_review_is_recorded_only_once(workspace, monkeypatch):
    async def interpret(_note, _stage):
        await asyncio.sleep(0)
        return {"summary": "Accept the incident impact"}

    monkeypatch.setattr(api, "interpret_review_feedback", interpret)

    async def run():
        ticket = await api.start_manual_ticket(ManualTicket(title="Checkout issue", body="Orders have data corruption"))
        ticket_id = ticket["ticket_id"]
        await api.advance_manual_ticket(ticket_id)
        await api.advance_manual_ticket(ticket_id)
        review = ManualReview(approver="Reviewer", approved=True, intent="accept", reason="Confirm the impact")
        results = await asyncio.gather(api.review_manual_ticket(ticket_id, review),
                                       api.review_manual_ticket(ticket_id, review), return_exceptions=True)
        assert sum(isinstance(result, HTTPException) and result.status_code == 409 for result in results) == 1
        assert len(api.app.state.manual_ticket_records[ticket_id]["reviews"]) == 1
        assert api._manual_ticket_snapshot(ticket_id)["current_stage"] == "assignment"

    asyncio.run(run())


def test_blank_input_and_conflicting_review_fail_without_progress(workspace):
    async def run():
        with pytest.raises(HTTPException) as blank:
            await api.start_manual_ticket(ManualTicket(title="   ", body="          "))
        assert blank.value.status_code == 422
        ticket = await api.start_manual_ticket(ManualTicket(title="Checkout issue", body="Orders have data corruption"))
        ticket_id = ticket["ticket_id"]
        await api.advance_manual_ticket(ticket_id)
        await api.advance_manual_ticket(ticket_id)
        with pytest.raises(HTTPException) as conflict:
            await api.review_manual_ticket(ticket_id, ManualReview(
                approver="Reviewer", approved=True, intent="reject", reason="Stop this proposal"))
        assert conflict.value.status_code == 422
        assert api._manual_ticket_snapshot(ticket_id)["status"] == "waiting_for_review"

    asyncio.run(run())


def test_message_history_is_chronological_without_consuming_worker_queue():
    class Redis:
        async def xrevrange(self, stream, count):
            assert stream == "t2d:messages" and count == 2
            return [("2000-0", {"message": '{"message_id":"second"}'}),
                    ("1000-0", {"message": '{"message_id":"first"}'})]

    bus = RedisStreamBus("redis://unused")
    bus._client = Redis()
    messages = asyncio.run(bus.recent(2))
    assert [item["message_id"] for item in messages] == ["first", "second"]
    assert messages[0]["occurred_at"] == "1970-01-01T00:00:01+00:00"
