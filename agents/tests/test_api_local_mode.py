"""The HTTP API in local mode: one command, no Docker, every route working."""
from fastapi.testclient import TestClient

from agents.app import create_app
from agents.tests.helpers import fixed_triage, interpret_as_given


def test_local_mode_end_to_end_over_http():
    app = create_app(classify=fixed_triage("Low", 0.82), interpret=interpret_as_given)
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["mode"] == "local"
        assert (health["storage"]["kind"], health["bus"]["kind"], health["nodes"]["kind"]) == \
            ("memory", "memory", "in_process")
        policy = client.get("/policy").json()
        assert (policy["tau"], policy["risk_max"], policy["canary"]["risk_max"]) == (0.7, 0.6, 0.3)
        assert [gate["gate"] for gate in policy["gates"]] == [
            "duplicate_review", "autonomy_gate", "secret_scan", "pr_merge", "canary_review", "release_signoff"]

        inbox = client.get("/feedback/inbox", params={"count": 3}).json()["items"]
        ticket = client.post("/sandbox/tickets", json={"feedback_id": inbox[0]["feedback_id"]}).json()
        ticket_id = ticket["ticket_id"]
        for _ in range(30):
            snapshot = client.post(f"/sandbox/tickets/{ticket_id}/advance").json()
            if snapshot["status"] == "waiting_for_review":
                snapshot = client.post(f"/sandbox/tickets/{ticket_id}/review", json={
                    "approver": "Dosen", "approved": True, "intent": "accept", "reason": "Looks right"}).json()
            if snapshot["status"] in {"completed", "duplicate"}:
                break
        assert snapshot["status"] in {"completed", "duplicate"}
        assert client.get(f"/sandbox/tickets/{ticket_id}").json()["status"] == snapshot["status"]
        assert client.get("/sandbox/tickets").json()["items"][0]["ticket_id"] == ticket_id
        assert client.get("/messages/history", params={"limit": 500}).json()["items"]
        assert client.get("/ticket-history").json()["items"][0]["ticket_id"] == ticket_id

        assert client.post("/demo/migrate/1").json()["mode"] == "mobile_agent"
        assert client.post("/demo/migrate/6").json()["mode"] == "node_exporter"
        telemetry = client.get("/monitoring/telemetry").json()
        alert = client.post(f"/monitoring/anomalies/{telemetry['anomalies'][0]['anomaly_id']}/ticket").json()
        assert alert["channel"] == "monitoring"
        assert client.get("/experiments").status_code == 200

        assert client.get("/sandbox/tickets/NOPE").status_code == 404
        assert client.post("/sandbox/tickets", json={"body": "   "}).status_code == 422
        assert client.post("/monitoring/anomalies/ANO-bogus/ticket").status_code == 404
        assert client.post(f"/sandbox/tickets/{ticket_id}/advance").status_code == 409
