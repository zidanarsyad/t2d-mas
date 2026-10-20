"""HTTP routes for the monitoring view: simulated telemetry and the alert -> ticket feedback loop."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request

from agents import tools

router = APIRouter()


@router.get("/monitoring/telemetry")
def telemetry(request: Request, scenario: Literal["flash_sale", "normal"] = "flash_sale",
              seed: int = 42) -> dict[str, Any]:
    """One hour of seeded, simulated metrics with anomalies flagged by z-score."""
    return tools.telemetry(scenario, seed, anomaly_z=request.app.state.pipeline.policy.anomaly_z)


@router.post("/monitoring/anomalies/{anomaly_id}/ticket")
async def ticket_from_anomaly(anomaly_id: str, request: Request) -> dict[str, Any]:
    """Scout-Monitor opens a ticket for an anomaly; asking twice returns the same ticket."""
    try:  # ids look like ANO-<scenario>-<seed>-<service>-<metric>
        scenario, seed, rest = anomaly_id.removeprefix("ANO-").split("-", 2)
        data = tools.telemetry(scenario, int(seed), anomaly_z=request.app.state.pipeline.policy.anomaly_z)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Unknown anomaly id.") from exc
    anomaly = next((item for item in data["anomalies"] if item["anomaly_id"] == anomaly_id), None)
    if anomaly is None or not rest:
        raise HTTPException(status_code=404, detail="Unknown anomaly id.")
    pipeline = request.app.state.pipeline
    await pipeline.emit("monitoring.anomaly", anomaly_id=anomaly_id, service=anomaly["service"],
                        metric=anomaly["metric"], z=anomaly["z"])
    snapshot = await pipeline.follow_up_from_anomaly(anomaly)
    await pipeline.emit("ticket.follow_up", parent_ticket_id=None, ticket_id=snapshot["ticket_id"],
                        anomaly_id=anomaly_id)
    return snapshot
