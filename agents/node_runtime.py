"""Demo node API: verify a bundle, run it locally, and return aggregate JSON only."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from agents.security_policy import SecurityError, validate_egress, verify_bundle_signature

app = FastAPI(title="T2D-MAS Node Runtime")


class ExecuteRequest(BaseModel):
    bundle_id: str
    agent_id: str
    code_b64: str
    state: dict[str, Any]
    signature: str


def _get_public_key() -> Any:
    """Load a raw Ed25519 public key shared with the orchestrator."""
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    encoded = os.getenv("AGENT_PUBLIC_KEY")
    if not encoded:
        key_file = Path(os.getenv("PUBLIC_KEY_DIR", "/run/t2d/public")) / "agent_public.key"
        if key_file.exists():
            encoded = key_file.read_text(encoding="utf-8").strip()
    if not encoded:
        raise RuntimeError("AGENT_PUBLIC_KEY is not configured")
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "node_id": os.getenv("NODE_ID", "node")}


@app.post("/execute")
async def execute(request: Request) -> dict[str, Any]:
    try:
        raw = await request.json()
        bundle = ExecuteRequest.model_validate(raw)
        payload = json.dumps({"bundle_id": bundle.bundle_id, "agent_id": bundle.agent_id,
                              "code_b64": bundle.code_b64, "state": bundle.state},
                             sort_keys=True, separators=(",", ":")).encode()
        if not verify_bundle_signature(payload, bundle.signature, _get_public_key()):
            raise SecurityError("invalid agent bundle signature")
        code = base64.b64decode(bundle.code_b64, validate=True).decode("utf-8")
        # The subprocess inherits Docker cgroup CPU/memory ceilings and gets a hard timeout.
        # Passing code directly avoids writing mobile bundles onto the node filesystem.
        completed = subprocess.run(
            [sys.executable, "-c", code], input=json.dumps(bundle.state), text=True,
            capture_output=True, timeout=20, check=False,
            env={"PATH": os.getenv("PATH", ""), "PYTHONIOENCODING": "utf-8",
                 "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if completed.returncode != 0:
            raise SecurityError("agent bundle failed in node sandbox")
        result = json.loads(completed.stdout)
        return {"result": validate_egress(result)}
    except (ValueError, KeyError, SecurityError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
