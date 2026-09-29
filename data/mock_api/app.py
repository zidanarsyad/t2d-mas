"""Small, failure-prone mock services for Jira, GitHub, CI, observability and infra.

Run from the repository root with: uvicorn data.mock_api.app:app --reload
"""
from __future__ import annotations

import asyncio
import os
import random
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


DATASET_VERSION = os.getenv("DATASET_VERSION", "course-demo-v1")
RNG = random.Random(int(os.getenv("MOCK_SEED", "42")))
LATENCY_MIN_MS = int(os.getenv("MOCK_LATENCY_MIN_MS", "50"))
LATENCY_MAX_MS = int(os.getenv("MOCK_LATENCY_MAX_MS", "300"))
ERROR_RATE = float(os.getenv("MOCK_ERROR_RATE", "0.02"))

app = FastAPI(title="T2D-MAS Mock Enterprise APIs", version="1.0.0")
state: dict[str, Any] = {
    "tickets": {}, "pull_requests": {}, "ci_runs": {}, "deployments": {},
    # Exposed read-only. The database schema also protects its durable counterpart.
    "audit_log": [],
}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d().\s-]{7,}\d)(?!\w)")
TOKEN_RE = re.compile(r"(?i)\b(?:bearer\s+\S+|(?:api[_-]?key|access[_-]?token|secret|token)\s*[:=]\s*\S+)")


def mask_text(value: Any) -> str:
    text = str(value or "")
    text = EMAIL_RE.sub("<EMAIL>", text)
    text = PHONE_RE.sub("<PHONE>", text)
    return TOKEN_RE.sub("<TOKEN>", text)


@app.exception_handler(HTTPException)
async def versioned_http_error(_request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                        content={"detail": exc.detail, "dataset_version": DATASET_VERSION})


class ActionRequest(BaseModel):
    ticket_id: str | None = None
    change_id: str | None = None
    environment: str = "staging"
    human_approved: bool = False
    confidence: float = Field(default=0.0, ge=0, le=1)
    risk: float = Field(default=1.0, ge=0, le=1)
    tau: float = Field(default=0.7, ge=0, le=1)
    risk_max: float = Field(default=0.3, ge=0, le=1)
    correlation_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


@app.middleware("http")
async def simulate_network_conditions(request, call_next):
    # A fixed seed makes each process's simulated failures reproducible for demos.
    await asyncio.sleep(RNG.uniform(LATENCY_MIN_MS, LATENCY_MAX_MS) / 1000)
    if RNG.random() < ERROR_RATE:
        return JSONResponse(
            status_code=503,
            content={"error": "simulated_upstream_failure", "dataset_version": DATASET_VERSION},
        )
    return await call_next(request)


def response(data: Any) -> dict[str, Any]:
    return {"dataset_version": DATASET_VERSION, "data": data}


def audit(action: str, request: ActionRequest, decision: str) -> None:
    gate_passed = request.confidence >= request.tau and request.risk <= request.risk_max
    state["audit_log"].append({
        "audit_id": str(uuid4()),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": request.correlation_id or str(uuid4()),
        "actor_id": "mock-agent",
        "action": action,
        "ticket_id": request.ticket_id,
        "decision": decision,
        "human_approved": request.human_approved,
        "details": {**request.details, "confidence": request.confidence,
                     "risk": request.risk, "tau": request.tau,
                     "risk_max": request.risk_max, "autonomy_gate_passed": gate_passed},
        "dataset_version": DATASET_VERSION,
    })


@app.get("/health")
async def health():
    return response({"status": "ok"})


# Jira-like ticket operations.
@app.get("/jira/tickets")
async def list_tickets():
    return response(list(state["tickets"].values()))


@app.get("/jira/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    return response(state["tickets"].get(ticket_id, {
        "ticket_id": ticket_id, "title": "Example checkout failure",
        "body": "Synthetic ticket body with aggregated features only.",
        "component": "checkout", "severity": "High",
        "created_at": "2026-09-14T13:05:11Z", "duplicate_of": None,
        "pii_masked": True,
    }))


@app.post("/jira/tickets")
async def create_ticket(ticket: dict[str, Any]):
    ticket_id = str(ticket.get("ticket_id") or f"TCK-{len(state['tickets']) + 1:04d}")
    # Keep only normalized ticket fields and mask text before the mock stores or returns it.
    safe_ticket = {key: ticket.get(key) for key in
                   ("title", "body", "component", "severity", "created_at", "duplicate_of")}
    safe_ticket["title"] = mask_text(safe_ticket.get("title"))
    safe_ticket["body"] = mask_text(safe_ticket.get("body"))
    state["tickets"][ticket_id] = {**safe_ticket, "ticket_id": ticket_id, "pii_masked": True}
    audit_request = ActionRequest(ticket_id=ticket_id, correlation_id=ticket.get("correlation_id"),
                                  details={"operation": "ticket_create"})
    audit("create_ticket", audit_request, "ticket_created")
    return response(state["tickets"][ticket_id])


# GitHub-like pull request operations.
@app.get("/github/pulls")
async def list_pull_requests():
    return response(list(state["pull_requests"].values()))


@app.post("/github/pulls")
async def create_pull_request(request: ActionRequest):
    change_id = request.change_id or f"change-{len(state['pull_requests']) + 1}"
    pr = {"change_id": change_id, "status": "draft", "merged": False,
          "human_approved": request.human_approved}
    state["pull_requests"][change_id] = pr
    audit("create_pull_request", request, "draft_created")
    return response(pr)


@app.post("/github/pulls/{change_id}/merge")
async def merge_pull_request(change_id: str, request: ActionRequest):
    if not request.human_approved:
        gate_decision = ("eligible_but_human_approval_still_required"
                         if request.confidence >= request.tau and request.risk <= request.risk_max
                         else "escalated_by_autonomy_gate")
        audit("merge_pull_request", request, gate_decision)
        raise HTTPException(status_code=403, detail="human_approved=true is required to merge")
    pr = state["pull_requests"].setdefault(change_id, {"change_id": change_id})
    pr.update(status="merged", merged=True, human_approved=True)
    audit("merge_pull_request", request, "merged")
    return response(pr)


# Observability mock returns aggregates rather than raw production logs.
@app.get("/observability/metrics/{service}")
async def service_metrics(service: str):
    return response({"service": service, "window_minutes": 15,
                     "error_rate": 0.018, "p95_latency_ms": 420,
                     "affected_users_estimate": 2143, "feature_source": "aggregated"})


# CI operations provide intentionally simple status transitions for demos.
@app.post("/ci/runs")
async def start_ci(request: ActionRequest):
    run_id = str(uuid4())
    run = {"run_id": run_id, "change_id": request.change_id,
           "status": "passed", "passed": 18, "failed": 0}
    state["ci_runs"][run_id] = run
    audit("start_ci", request, "run_created")
    return response(run)


@app.get("/ci/runs/{run_id}")
async def get_ci(run_id: str):
    if run_id not in state["ci_runs"]:
        raise HTTPException(status_code=404, detail="CI run not found")
    return response(state["ci_runs"][run_id])


# Infra/deploy operations remain behind the human approval gate.
@app.post("/infra/deployments")
async def deploy(request: ActionRequest):
    deployment_id = str(uuid4())
    if not request.human_approved:
        gate_decision = ("eligible_but_human_approval_still_required"
                         if request.confidence >= request.tau and request.risk <= request.risk_max
                         else "escalated_by_autonomy_gate")
        audit("deploy", request, gate_decision)
        raise HTTPException(status_code=403, detail="human_approved=true is required to deploy")
    deployment = {"deployment_id": deployment_id, "change_id": request.change_id,
                  "environment": request.environment, "status": "deployed",
                  "human_approved": True}
    state["deployments"][deployment_id] = deployment
    audit("deploy", request, "deployed")
    return response(deployment)


@app.get("/infra/deployments")
async def list_deployments():
    return response(list(state["deployments"].values()))


@app.get("/audit-log")
async def read_audit_log():
    return response(list(state["audit_log"]))
