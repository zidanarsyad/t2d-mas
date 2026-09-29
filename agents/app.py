"""FastAPI orchestrator API: health, approval queue, and a mobile-node demo route."""
from __future__ import annotations

import base64
import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from agents.audit import PostgresAuditSink
from agents.bus import ACLMessage, RedisStreamBus
from agents.events import event_hub
from agents.logging_config import configure_logging
from agents.mobility import MobileAgentRuntime
from agents.orchestrator import T2DOrchestrator

configure_logging()
PRIVATE_KEY_DIR = Path(os.getenv("PRIVATE_KEY_DIR", "/run/t2d/private"))
PUBLIC_KEY_DIR = Path(os.getenv("PUBLIC_KEY_DIR", "/run/t2d/public"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    PRIVATE_KEY_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_KEY_DIR.mkdir(parents=True, exist_ok=True)
    private_file = PRIVATE_KEY_DIR / "agent_private.key"
    public_file = PUBLIC_KEY_DIR / "agent_public.key"
    if private_file.exists():
        private = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_file.read_text()))
    else:
        private = Ed25519PrivateKey.generate()
        private_file.write_text(base64.b64encode(private.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
            serialization.NoEncryption())).decode())
        private_file.chmod(0o600)
    public_file.write_text(base64.b64encode(private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())
    app.state.audit = PostgresAuditSink()
    app.state.pipeline = T2DOrchestrator(app.state.audit)
    app.state.bus = RedisStreamBus(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    await app.state.bus.connect()
    await app.state.bus.ensure_group("workers")
    app.state.mobile = MobileAgentRuntime(private, private.public_key(), audit_sink=app.state.audit)
    yield
    await app.state.bus.close()


app = FastAPI(title="T2D-MAS Orchestrator", lifespan=lifespan)


class StartTicket(BaseModel):
    ticket_id: str


class Approval(BaseModel):
    approver: str
    approved: bool
    reason: str = ""


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "orchestrator"}


@app.get("/events")
async def events() -> StreamingResponse:
    async def stream():
        yield "event: ready\ndata: {\"status\":\"connected\"}\n\n"
        iterator = event_hub.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(anext(iterator), timeout=20)
                    yield f"event: update\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            await iterator.aclose()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@app.post("/tickets")
async def start_ticket(body: StartTicket) -> dict[str, Any]:
    run = app.state.pipeline.start(body.ticket_id)
    await event_hub.publish({"type": "ticket.started", "ticket_id": run.ticket_id,
                             "stage": run.stage.value})
    return {"ticket_id": run.ticket_id, "stage": run.stage.value}


@app.get("/approvals")
def approvals() -> list[dict[str, Any]]:
    return [item for run in app.state.pipeline.runs.values() for item in run.approval_queue]


@app.post("/messages")
async def publish_message(body: dict[str, Any]) -> dict[str, str]:
    try:
        message = ACLMessage(**body)
        stream_id = await app.state.bus.publish(message)
        await event_hub.publish({"type": "message.published", "correlation_id": message.correlation_id,
                                 "performative": message.performative})
        return {"stream_id": stream_id, "message_id": message.message_id}
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/messages/next")
async def read_message(consumer: str) -> list[dict[str, Any]]:
    messages = await app.state.bus.read_group("workers", consumer, count=5, block_ms=250)
    return [{"stream_id": item_id, "message": message.__dict__} for item_id, message in messages]


@app.post("/messages/{entry_id}/ack")
async def acknowledge_message(entry_id: str) -> dict[str, int]:
    return {"acknowledged": await app.state.bus.ack("workers", entry_id)}


@app.post("/tickets/{ticket_id}/approve")
async def approve(ticket_id: str, body: Approval) -> dict[str, Any]:
    try:
        run = app.state.pipeline.approve(ticket_id, body.approver, body.approved, body.reason)
        await event_hub.publish({"type": "approval.resolved", "ticket_id": run.ticket_id,
                                 "approved": body.approved, "waiting_for": run.waiting_for})
        return {"ticket_id": run.ticket_id, "waiting_for": run.waiting_for,
                "human_approved": run.human_approved}
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/tickets/{ticket_id}/resume")
async def resume(ticket_id: str) -> dict[str, Any]:
    try:
        run = app.state.pipeline.resume_approved(ticket_id)
        await event_hub.publish({"type": "pipeline.advanced", "ticket_id": run.ticket_id,
                                 "stage": run.stage.value})
        return {"ticket_id": run.ticket_id, "stage": run.stage.value}
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/demo/migrate/{node_id}")
async def demo_migrate(node_id: int) -> dict[str, Any]:
    if not 1 <= node_id <= 6:
        raise HTTPException(status_code=404, detail="node_id must be 1..6")
    nodes = os.getenv("NODE_URLS", "").split(",")
    if len(nodes) != 6 or not nodes[node_id - 1]:
        raise HTTPException(status_code=503, detail="node runtime URLs are not configured")
    code = """import json, sys
state = json.load(sys.stdin)
print(json.dumps({key: state[key] for key in (
    'service', 'request_count', 'error_rate', 'latency_p95_ms', 'evidence_hash'
)}))
"""
    state = {"service": f"service-{node_id}", "request_count": 1200 + node_id,
             "error_rate": 0.01 * node_id, "latency_p95_ms": 100 + node_id,
             "evidence_hash": f"demo-aggregate-{node_id}"}
    try:
        result = await app.state.mobile.migrate(nodes[node_id - 1], "Scout-Log", code, state,
                                                correlation_id=f"mobile-node-{node_id}")
        await event_hub.publish({"type": "agent.migrated", "agent_id": "Scout-Log",
                                 "node_id": node_id, "bytes_sent": app.state.mobile.stats.bytes_sent,
                                 "bytes_returned": app.state.mobile.stats.bytes_returned})
        return {"node_id": node_id, "result": result,
                "bytes_sent": app.state.mobile.stats.bytes_sent,
                "bytes_returned": app.state.mobile.stats.bytes_returned}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
