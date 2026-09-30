import json
import sys
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from agents import app as api
from agents.audit import MemoryAuditSink
from agents.orchestrator import T2DOrchestrator
from agents.severity_triage import classify_ticket
from agents.synthetic_data import make_synthetic_tickets


def test_manual_snapshot_hides_internal_state_and_activity_is_idempotent(monkeypatch):
    audit = MemoryAuditSink()
    pipeline = T2DOrchestrator(audit)
    pipeline.start("TEST-1")
    record = {"ticket_id": "TEST-1", "title": "Checkout", "body": "Fails on submit",
              "severity": "High", "severity_confidence": 0.8,
              "severity_rationale": "outage cue", "severity_cues": ["outage"],
              "reviews": [], "_recorded_stages": set(), "_policy_recorded": False}
    monkeypatch.setattr(api.app.state, "manual_ticket_records", {"TEST-1": record}, raising=False)
    monkeypatch.setattr(api.app.state, "pipeline", pipeline, raising=False)
    monkeypatch.setattr(api.app.state, "audit", audit, raising=False)

    api._record_manual_stage_activity("TEST-1", record, "intake")
    api._record_manual_stage_activity("TEST-1", record, "intake")
    snapshot = api._manual_ticket_snapshot("TEST-1")

    assert len([event for event in audit.events if event.action == "agent_output"]) == 1
    assert "_recorded_stages" not in snapshot
    assert "_policy_recorded" not in snapshot
    json.dumps(snapshot)


def test_history_sample_caps_at_fifty_with_requested_mix():
    rows = [dict(ticket, seed=42) for ticket in make_synthetic_tickets(42, 100)]

    sample = api._history_sample(rows, set(api.HISTORY_SEVERITY_ORDER))

    assert len(sample) == 50
    # Seed 42 has only 25 Low tickets; the unused quota goes to Medium.
    assert {severity: sum(row["severity"] == severity for row in sample)
            for severity in api.HISTORY_SEVERITY_ORDER} == {
                "Low": 25, "Medium": 17, "High": 6, "Critical": 2,
            }


def test_saved_history_returns_agent_output_and_process_timestamp(monkeypatch):
    now = datetime.now(timezone.utc)
    ticket_rows = [("TEST-2", "Title", "Body", "Medium", now)]
    audit_rows = [(now, "Broker-Triage", "agent_output", "completed", {
        "ticket_id": "TEST-2",
        "details": {"stage": "triage", "execution_mode": "rule_based_prototype",
                    "output": {"severity": "Medium"}},
    }), (now, "orchestrator", "review_revision_requested", "revision_requested", {
        "ticket_id": "TEST-2",
        "details": {"stage": "triage", "checkpoint": "autonomy_gate",
                    "approver": "reviewer", "reason": "Severity should be High.",
                    "intent": "request_changes", "revision": 1,
                    "interpretation": {"summary": "Raise severity based on customer impact."}},
    })]

    class Cursor:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, query, _params):
            return Cursor(ticket_rows if query.lstrip().startswith("SELECT ticket_id") else audit_rows)

    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda _url: Connection()))

    result = api.saved_ticket_history()

    assert result["total"] == 1
    assert result["items"][0]["process_started_at"] == now.isoformat()
    assert result["items"][0]["events"][0]["output"] == {"severity": "Medium"}
    review_event = result["items"][0]["events"][1]
    assert review_event["intent"] == "request_changes"
    assert review_event["note"] == "Severity should be High."
    assert review_event["interpretation"]["summary"] == "Raise severity based on customer impact."
    assert review_event["revision"] == 1


def test_published_message_is_audited_before_redis_and_masks_text(monkeypatch):
    audit = MemoryAuditSink()

    class Bus:
        async def publish(self, message):
            assert audit.events[-1].decision == "publish_authorized"
            assert audit.events[-1].details["content"]["note"] == "Contact <EMAIL>"
            return "1-0"

    async def publish_event(_event):
        return None

    monkeypatch.setattr(api.app.state, "audit", audit, raising=False)
    monkeypatch.setattr(api.app.state, "bus", Bus(), raising=False)
    monkeypatch.setattr(api.event_hub, "publish", publish_event)

    result = asyncio.run(api.publish_message({
        "performative": "inform", "correlation_id": "TEST-3",
        "sender": "Worker-Investigate", "receiver": ["Broker-Assign"],
        "content": {"note": "Contact alice@example.com"},
    }))

    assert result["stream_id"] == "1-0"
    assert [event.decision for event in audit.events] == ["publish_authorized", "published"]


def test_checkout_outage_is_classified_as_high_impact():
    result = classify_ticket("Checkout outage during the sale")

    assert result["severity"] == "High"
    assert "outage" in result["matched_cues"]
