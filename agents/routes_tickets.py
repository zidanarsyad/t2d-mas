"""HTTP routes for tickets: create from feedback, advance stage by stage, review at a gate."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from agents import feedback_samples
from agents.pipeline import TicketPipeline

router = APIRouter()
Channel = Literal["manual", "portal_form", "email", "app_store_review", "cs_chat", "slack", "crash_reporter",
                  "monitoring"]


class NewTicket(BaseModel):
    body: str | None = Field(default=None, max_length=4000)   # optional when feedback_id is given
    title: str | None = Field(default=None, max_length=180)   # derived from the text when empty
    channel: Channel = "manual"
    feedback_id: str | None = None                            # an inbox message to start from
    inject_test_secret: bool = False                          # demo: Security-Policy must block the draft
    simulate_regression: bool = False                         # demo: monitoring finds a post-release problem


class Review(BaseModel):
    approver: str = Field(min_length=1, max_length=80)
    approved: bool
    intent: Literal["accept", "request_changes", "reject"] | None = None
    reason: str = Field(min_length=3, max_length=500)


def _pipeline(request: Request) -> TicketPipeline:
    return request.app.state.pipeline


@router.get("/feedback/inbox")
def feedback_inbox(seed: int = 42, count: int = Query(default=8, ge=1, le=20),
                   scenario: Literal["all", "flash_sale"] = "all") -> dict[str, Any]:
    """Mock user feedback as a support inbox would show it (no hidden labels)."""
    return {"seed": seed, "count": count, "scenario": scenario,
            "items": feedback_samples.inbox(seed=seed, count=count, scenario=scenario)}


@router.post("/sandbox/tickets")
async def create_ticket(body: NewTicket, request: Request) -> dict[str, Any]:
    return await _pipeline(request).create_ticket(
        body=body.body, title=body.title, channel=body.channel, feedback_id=body.feedback_id,
        options={"inject_test_secret": body.inject_test_secret, "simulate_regression": body.simulate_regression})


@router.get("/sandbox/tickets")
def list_tickets(request: Request) -> dict[str, Any]:
    """One source of truth for the board, the review inbox and the run view."""
    return {"items": _pipeline(request).list_tickets()}


@router.get("/sandbox/tickets/{ticket_id}")
def get_ticket(ticket_id: str, request: Request) -> dict[str, Any]:
    return _pipeline(request).snapshot(ticket_id)


@router.post("/sandbox/tickets/{ticket_id}/advance")
async def advance_ticket(ticket_id: str, request: Request) -> dict[str, Any]:
    return await _pipeline(request).advance(ticket_id)


@router.post("/sandbox/tickets/{ticket_id}/review")
async def review_ticket(ticket_id: str, body: Review, request: Request) -> dict[str, Any]:
    return await _pipeline(request).review(ticket_id, body.approver, body.approved, body.intent, body.reason)
