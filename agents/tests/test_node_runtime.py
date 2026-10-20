"""A data node runs signed bundles next to its own logs and lets only aggregates out."""
from dataclasses import asdict

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from agents.mobility import AgentBundle
from agents.node_runtime import create_node_app
from agents.scouts import SCOUT_LOG_SOURCE


def test_node_runs_the_signed_scout_log_bundle_on_its_own_logs():
    key = Ed25519PrivateKey.generate()
    client = TestClient(create_node_app("node-3", public_key=key.public_key()))
    assert client.get("/inventory").json() == {"node_id": "node-3", "service": "payment-db",
                                               "log_mb": 1365, "records": 600}

    bundle = AgentBundle.create("Scout-Log", SCOUT_LOG_SOURCE, {"seed": 1, "component": "payment"}, key)
    response = client.post("/execute", json=asdict(bundle))
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["service"] == "payment-db" and result["request_count"] == 600
    assert "users.example.net" not in response.text  # raw rows stay on the node

    exporter = client.post("/aggregates", json={"seed": 1, "component": "payment"}).json()["result"]
    assert exporter == result  # the exporter and the bundle compute the same aggregates


def test_node_refuses_raw_egress_and_unsigned_code():
    key, stranger = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    client = TestClient(create_node_app("node-1", public_key=key.public_key()))
    raw = AgentBundle.create("Scout-Log", "import json; print(json.dumps({'raw_log': 'private record'}))", {}, key)
    assert client.post("/execute", json=asdict(raw)).status_code == 400
    forged = AgentBundle.create("Scout-Log", SCOUT_LOG_SOURCE, {"seed": 1, "component": "payment"}, stranger)
    assert client.post("/execute", json=asdict(forged)).status_code == 400
