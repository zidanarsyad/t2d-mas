import json
import sys
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from agents import app as api
from agents.audit import MemoryAuditSink
from agents.orchestrator import T2DOrchestrator
from agents.severity_triage import classify_ticket, classify_ticket_with_llm
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


def test_explicit_reviewer_severity_correction_applies_without_openrouter(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = asyncio.run(classify_ticket_with_llm(
        "Seller payout issue with unclear impact",
        review_feedback={"summary": "The reviewer knows sellers are affected.",
                         "requested_changes": ["This should be Critical since it can affect sellers."]},
    ))

    assert result["severity"] == "Critical"
    assert result["reviewer_override"] == "Critical"
    assert result["provider"] == "rules_fallback"
    assert result["fallback_reason"] == "OPENROUTER_API_KEY is unset"


def test_openrouter_uses_qwen_first_and_ling_as_model_fallback(monkeypatch):
    from agents import severity_triage

    request_body = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"model": "inclusionai/ling-3.0-flash-sante:free",
                    "choices": [{"message": {"content":
                        '{"severity":"High","category":"seller impact","rationale":"Seller transactions may fail."}'}}]}

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, headers, json):
            request_body.update(json)
            assert headers["Authorization"] == "Bearer test-key"
            return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "qwen/qwen3.8-27b:free")
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODEL", "inclusionai/ling-3.0-flash-sante:free")
    monkeypatch.setattr(severity_triage.httpx, "AsyncClient", Client)

    result = asyncio.run(severity_triage.classify_ticket_with_llm("Seller payments are failing."))

    assert request_body["models"] == [
        "qwen/qwen3.8-27b:free", "inclusionai/ling-3.0-flash-sante:free",
    ]
    assert request_body["max_tokens"] == 512
    assert "response_format" not in request_body
    assert result["model"] == "inclusionai/ling-3.0-flash-sante:free"
    assert result["preferred_model"] == "qwen/qwen3.8-27b:free"
    assert result["fallback_used"] is True
