"""Saved results: the evaluation sample shown in the dashboard and the saved ticket history."""
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

from agents.repository import PostgresRepository
from agents.routes_results import HISTORY_SEVERITY_ORDER, _history_sample
from agents.synthetic_data import make_synthetic_tickets


def test_history_sample_caps_at_fifty_with_requested_mix():
    rows = [dict(ticket, seed=42) for ticket in make_synthetic_tickets(42, 100)]
    sample = _history_sample(rows, set(HISTORY_SEVERITY_ORDER))
    assert len(sample) == 50
    # Seed 42 has only 25 Low tickets; the unused quota goes to Medium.
    assert {severity: sum(row["severity"] == severity for row in sample) for severity in HISTORY_SEVERITY_ORDER} \
        == {"Low": 25, "Medium": 17, "High": 6, "Critical": 2}


def test_saved_history_from_postgres_keeps_outputs_reviews_and_gate_evidence(monkeypatch):
    now = datetime.now(timezone.utc)
    ticket_rows = [("TEST-2", "Title", "Body", "Medium", now)]
    audit_rows = [
        (now, "Broker-Triage", "agent_output", "completed",
         {"ticket_id": "TEST-2", "details": {"stage": "triage", "execution_mode": "live",
                                             "output": {"severity": "Medium"}}}, "TEST-2"),
        (now, "Security-Policy", "policy_gate", "escalated",
         {"ticket_id": "TEST-2", "confidence": 0.45,
          "details": {"stage": "triage", "gate": "autonomy_gate",
                      "inputs": {"confidence": 0.45, "tau": 0.7, "risk": 0.3, "risk_max": 0.6}}}, "TEST-2"),
        (now, "orchestrator", "review_revision_requested", "revision_requested",
         {"ticket_id": "TEST-2", "details": {"stage": "triage", "checkpoint": "autonomy_gate", "approver": "reviewer",
                                             "reason": "Severity should be High.", "intent": "request_changes",
                                             "revision": 1, "interpretation": {"summary": "Raise severity."}}},
         "TEST-2"),
    ]

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
            return Cursor(ticket_rows if query.lstrip().startswith("SELECT ticket_id, title") else audit_rows)

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda _url: Connection()))

    result = PostgresRepository("postgresql://test").ticket_history(50)

    item = result["items"][0]
    assert result["total"] == 1 and item["process_started_at"] == now.isoformat()
    assert item["events"][0]["output"] == {"severity": "Medium"}
    gate = item["events"][1]
    assert (gate["checkpoint"], gate["confidence"], gate["tau"], gate["risk_max"]) == ("autonomy_gate", 0.45, 0.7, 0.6)
    review = item["events"][2]
    assert (review["intent"], review["note"], review["revision"]) == ("request_changes", "Severity should be High.", 1)
