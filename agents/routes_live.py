"""HTTP routes for live views: the event stream, the message log and the mobile-agent demo."""
from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import StreamingResponse

from agents.scouts import ScoutLog
from agents.stage_agent import StageContext

router = APIRouter()


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    """Server-sent events: every stage, gate, message and review as it happens."""
    hub = request.app.state.events

    async def stream():
        yield "event: ready\ndata: {\"status\":\"connected\"}\n\n"
        iterator = hub.subscribe(heartbeat_seconds=20)
        try:
            async for event in iterator:
                if event is not None:
                    yield f"event: update\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"
                else:
                    yield ": keep-alive\n\n"
        finally:
            await iterator.aclose()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/messages/history")
async def message_history(request: Request, limit: Annotated[int, Query(ge=1, le=500)] = 200) -> dict[str, Any]:
    """Recent agent messages, oldest first, so a reloaded page can rebuild the conversation."""
    return {"items": await request.app.state.bus.recent(count=limit)}


@router.post("/demo/migrate/{node_number}")
async def demo_migrate(node_number: int, request: Request,
                       component: str = "payment") -> dict[str, Any]:
    """Send Scout-Log to one node outside any ticket, to show the migration rule and byte counts."""
    pipeline = request.app.state.pipeline
    if not 1 <= node_number <= len(pipeline.nodes):
        raise HTTPException(status_code=404, detail=f"node must be 1..{len(pipeline.nodes)}")
    node = pipeline.nodes[node_number - 1]
    context = StageContext(ticket={"ticket_id": f"DEMO-{node.node_id}"}, outputs={}, policy=pipeline.policy,
                           seed=42, deps=pipeline)
    visit = await ScoutLog().visit(context, node, component)
    if visit["mode"] == "failed":
        raise HTTPException(status_code=502, detail=visit["error"])
    return {**visit, "node_number": node_number, "result": visit["aggregate"]}
