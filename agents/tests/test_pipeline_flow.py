"""End-to-end runs of the nine-stage pipeline in local mode."""
import asyncio
import json

import pytest

from agents.pipeline import Conflict, InvalidInput
from agents.tests.helpers import fixed_triage, interpret_as_given, walk

STAGES = ["intake", "triage", "assignment", "investigation", "planning", "implementation", "qa", "deployment",
          "monitoring"]
CHECKOUT = "Checkout outage: customers cannot complete checkout during the sale."


def test_full_run_records_every_agent_and_needs_people_for_merge_and_release(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("High", 0.68), interpret=interpret_as_given)

    async def run():
        ticket = await pipeline.create_ticket(body=CHECKOUT)
        return await walk(pipeline, ticket["ticket_id"])

    final, gates = asyncio.run(run())
    assert final["status"] == "completed"
    assert gates[0] == "autonomy_gate"                       # High at 0.68 is below tau
    assert "pr_merge" in gates and gates[-1] == "release_signoff"
    outputs = final["agent_outputs"]
    assert list(outputs) == STAGES
    for output in outputs.values():  # every agent reports its five components
        assert set(output["components"]) == {"perceive", "remember", "reason", "act", "report"}
        assert output["summary"] and isinstance(output["decisions"], list)
    assert outputs["investigation"]["agent"] == outputs["assignment"]["winner"] == final["assignee"]
    assert [action["action"] for action in final["irreversible_actions"]] == ["merge", "full_deploy"]
    assert all(action["executed"] and action["human_approved"] for action in final["irreversible_actions"])
    change = pipeline.repository.code_changes[outputs["implementation"]["draft_pr"]["change_id"]]
    assert change["merged"] and change["human_approved"]
    production = [row for row in pipeline.repository.deployments.values() if row["environment"] == "production"]
    assert production and production[0]["human_approved"] and production[0]["approved_by"] == "reviewer"
    # Every message is audited twice: before and after it reaches the bus.
    assert sum(event.action == "agent_message" for event in pipeline.audit.events) == pipeline.deps.bus.count * 2
    json.dumps(final)


def test_rejected_review_stops_the_run_and_masks_the_note(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("High", 0.68))

    async def run():
        ticket = await pipeline.create_ticket(body=CHECKOUT)
        await pipeline.advance(ticket["ticket_id"])
        await pipeline.advance(ticket["ticket_id"])
        return await pipeline.review(ticket["ticket_id"], "reviewer", False, "reject",
                                     "Reject; contact alice@example.com")

    rejected = asyncio.run(run())
    assert rejected["status"] == "rejected" and rejected["current_stage"] == "triage"
    approval = next(event for event in pipeline.audit.events if event.action == "human_approval")
    assert approval.decision == "rejected"
    assert approval.details["reason"] == "Reject; contact <EMAIL>"
    message = next(event for event in pipeline.audit.events
                   if event.action == "agent_message" and event.actor_id == "reviewer")
    assert message.details["content"]["note"] == "Reject; contact <EMAIL>"


def test_request_changes_revises_triage_with_the_reviewers_interpretation(make_pipeline):
    async def classify(_text, review_feedback=None):
        result = {"severity": "High" if review_feedback else "Medium", "confidence": 0.65,
                  "matched_cues": ["outage"], "rationale": "stub", "agent": "stub",
                  "provider": "openrouter" if review_feedback else "rules"}
        if review_feedback:
            result["review_interpretation"] = {"summary": "Treat this as a high-impact outage.",
                                               "requested_changes": ["Reclassify severity as High"],
                                               "constraints": [], "evidence": [], "needs_clarification": False}
        return result

    pipeline = make_pipeline(classify=classify)

    async def run():
        ticket = await pipeline.create_ticket(body="All customers are unable to finish checkout.")
        await pipeline.advance(ticket["ticket_id"])
        await pipeline.advance(ticket["ticket_id"])
        return await pipeline.review(ticket["ticket_id"], "reviewer", False, "request_changes",
                                     "All customers are affected, so classify this as High.")

    revised = asyncio.run(run())
    assert revised["status"] == "running" and revised["current_stage"] == "triage"
    assert revised["severity"] == "High"
    assert revised["agent_outputs"]["triage"]["revision"] == 1
    review = revised["reviews"][-1]
    assert review["intent"] == "request_changes"
    assert review["interpretation"]["requested_changes"] == ["Reclassify severity as High"]
    history = next(event for event in pipeline.audit.events if event.action == "review_revision_requested")
    assert history.details["interpretation"] == review["interpretation"]


def test_waiting_ticket_is_stable_and_hides_internal_state(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("Critical", 0.84))

    async def run():
        ticket = await pipeline.create_ticket(body="Orders have data corruption after checkout.")
        await pipeline.advance(ticket["ticket_id"])
        paused = await pipeline.advance(ticket["ticket_id"])
        before = len(pipeline.audit.events)
        repeated = await pipeline.advance(ticket["ticket_id"])
        return paused, repeated, before

    paused, repeated, before = asyncio.run(run())
    assert len(pipeline.audit.events) == before and repeated == paused
    assert paused["waiting_for"] == "autonomy_gate" and paused["review_requested_at"]
    assert paused["pending_gate"]["allowed_intents"] == ["accept", "reject", "request_changes"]
    assert pipeline.list_tickets()[0] == paused
    assert not any(key.startswith("_") for key in paused)
    json.dumps(paused)


def test_two_reviews_at_once_are_recorded_only_once(make_pipeline):
    async def slow_interpret(note, stage):
        await asyncio.sleep(0)
        return await interpret_as_given(note, stage)

    pipeline = make_pipeline(classify=fixed_triage("Critical", 0.84), interpret=slow_interpret)

    async def run():
        ticket_id = (await pipeline.create_ticket(body="Orders have data corruption after checkout."))["ticket_id"]
        await pipeline.advance(ticket_id)
        await pipeline.advance(ticket_id)
        results = await asyncio.gather(
            pipeline.review(ticket_id, "Reviewer", True, "accept", "Confirm the impact"),
            pipeline.review(ticket_id, "Reviewer", True, "accept", "Confirm the impact"), return_exceptions=True)
        return ticket_id, results

    ticket_id, results = asyncio.run(run())
    assert sum(isinstance(result, Conflict) for result in results) == 1
    assert len(pipeline.records[ticket_id]["reviews"]) == 1
    assert pipeline.snapshot(ticket_id)["current_stage"] == "assignment"


def test_blank_input_and_contradictory_reviews_are_refused(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("Critical", 0.84))

    async def run():
        with pytest.raises(InvalidInput):
            await pipeline.create_ticket(body="          ")
        ticket_id = (await pipeline.create_ticket(body="Orders have data corruption after checkout."))["ticket_id"]
        await pipeline.advance(ticket_id)
        await pipeline.advance(ticket_id)
        with pytest.raises(InvalidInput):
            await pipeline.review(ticket_id, "Reviewer", True, "reject", "Stop this proposal")
        return ticket_id

    ticket_id = asyncio.run(run())
    assert pipeline.snapshot(ticket_id)["status"] == "waiting_for_review"
