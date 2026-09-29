from dataclasses import asdict
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from agents.mobility import AgentBundle
from agents.node_runtime import app


def test_node_executes_signed_bundle_and_blocks_raw_egress(monkeypatch):
    # Windows sandbox temp permissions vary; keep this short-lived test sandbox in the workspace.
    monkeypatch.setattr(tempfile, "tempdir", str(Path(__file__).parent))
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr("agents.node_runtime._get_public_key", lambda: key.public_key())
    client = TestClient(app)

    code = "import json,sys; data=json.load(sys.stdin); print(json.dumps({'service':data['service'],'request_count':data['request_count']}))"
    bundle = AgentBundle.create("Scout-Log", code, {"service": "checkout", "request_count": 42}, key)
    response = client.post("/execute", json=asdict(bundle))
    assert response.status_code == 200
    assert response.json()["result"] == {"service": "checkout", "request_count": 42}

    raw_code = "import json; print(json.dumps({'raw_log':'private record'}))"
    raw_bundle = AgentBundle.create("Scout-Log", raw_code, {}, key)
    blocked = client.post("/execute", json=asdict(raw_bundle))
    assert blocked.status_code == 400
