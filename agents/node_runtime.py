"""A data node: it keeps its own service logs and lets only aggregates leave.

There are two ways to ask a node about its logs:
- POST /execute runs a signed Scout-Log bundle next to the logs ("move the code to the data");
- POST /aggregates uses the node's built-in exporter, for when shipping an agent is not worth it.
Both return allowlisted aggregate fields only. Docker runs six of these containers;
in local mode the orchestrator runs the same app in-process.
"""
from __future__ import annotations

import asyncio
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
from agents.tools import NODE_LOG_MB, NODE_SERVICE, node_logs, standard_aggregates

LOG_RECORDS = 600  # rows of simulated request logs held on each node per investigation window


class ExecuteRequest(BaseModel):
    bundle_id: str
    agent_id: str
    code_b64: str
    state: dict[str, Any]
    signature: str


class AggregateRequest(BaseModel):
    seed: int
    component: str


def _load_public_key() -> Any:
    """Load the orchestrator's raw Ed25519 public key (environment variable or mounted file)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    encoded = os.getenv("AGENT_PUBLIC_KEY")
    if not encoded:
        key_file = Path(os.getenv("PUBLIC_KEY_DIR", "/run/t2d/public")) / "agent_public.key"
        if key_file.exists():
            encoded = key_file.read_text(encoding="utf-8").strip()
    if not encoded:
        raise RuntimeError("AGENT_PUBLIC_KEY is not configured")
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded))


def _run_sandboxed(code: str, payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    # The subprocess inherits the container's CPU/memory limits and gets a hard timeout.
    # Code is passed on the command line, so bundles are never written to the node's disk.
    # -I -S: isolated mode without site-packages, so bundles get the standard library only.
    env = {"PATH": os.getenv("PATH", ""), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if os.getenv("SYSTEMROOT"):  # Windows needs this to start Python in local mode
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return subprocess.run([sys.executable, "-I", "-S", "-c", code], input=json.dumps(payload), text=True,
                          capture_output=True, timeout=20, check=False, env=env)


def create_node_app(node_id: str, public_key: Any | None = None) -> FastAPI:
    service = NODE_SERVICE.get(node_id, "api-gateway")
    app = FastAPI(title=f"T2D-MAS node {node_id}")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "node_id": node_id, "service": service}

    @app.get("/inventory")
    def inventory() -> dict[str, Any]:
        """Metadata only: how much log data this node holds (used by the migration rule)."""
        return {"node_id": node_id, "service": service, "log_mb": NODE_LOG_MB[service], "records": LOG_RECORDS}

    @app.post("/aggregates")
    def aggregates(body: AggregateRequest) -> dict[str, Any]:
        logs = node_logs(service, body.seed, body.component, LOG_RECORDS)
        return {"result": validate_egress(standard_aggregates(service, logs))}

    @app.post("/execute")
    async def execute(request: Request) -> dict[str, Any]:
        try:
            bundle = ExecuteRequest.model_validate(await request.json())
            payload = json.dumps({"bundle_id": bundle.bundle_id, "agent_id": bundle.agent_id,
                                  "code_b64": bundle.code_b64, "state": bundle.state},
                                 sort_keys=True, separators=(",", ":")).encode()
            if not verify_bundle_signature(payload, bundle.signature, public_key or _load_public_key()):
                raise SecurityError("invalid agent bundle signature")
            code = base64.b64decode(bundle.code_b64, validate=True).decode("utf-8")
            logs = node_logs(service, int(bundle.state.get("seed", 0)),
                             str(bundle.state.get("component", "other")), LOG_RECORDS)
            completed = await asyncio.to_thread(
                _run_sandboxed, code, {**bundle.state, "service": service, "local_logs": logs})
            if completed.returncode != 0:
                raise SecurityError("agent bundle failed in node sandbox")
            return {"result": validate_egress(json.loads(completed.stdout))}
        except (ValueError, KeyError, SecurityError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return app


# Docker starts one container per node with NODE_ID set (see docker-compose.yml).
app = create_node_app(os.getenv("NODE_ID", "node-1"))
