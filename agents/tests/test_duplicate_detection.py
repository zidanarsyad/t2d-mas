"""Duplicate detection: cosine similarity with the report's three bands."""
import asyncio

import pytest

from agents import feedback_samples
from agents.policy import duplicate_band
from agents.similarity import TfidfCosine, cosine_dense
from agents.tests.helpers import fixed_triage, interpret_as_given


def text(feedback_id):
    sample = feedback_samples.get(feedback_id)
    return f"{sample.title or ''}\n{sample.text}"


def test_idea_report_worked_example():
    a, b, c = [0.80, 0.10, 0.00, 0.30, 0.20], [0.75, 0.15, 0.00, 0.35, 0.25], [0.10, 0.00, 0.90, 0.05, 0.00]
    assert cosine_dense(a, b) == pytest.approx(0.994, abs=0.001)
    assert cosine_dense(a, c) == pytest.approx(0.119, abs=0.001)


def test_band_edges():
    assert [duplicate_band(score) for score in (0.85, 0.849, 0.70, 0.699)] == ["auto_link", "review", "review", "new"]


def test_corpus_pairs_fall_into_all_three_bands():
    model = TfidfCosine(feedback_samples.background_texts())
    assert duplicate_band(model.similarity(text("FB-001"), text("FB-002"))) == "auto_link"   # a repost
    assert duplicate_band(model.similarity(text("FB-011"), text("FB-012"))) == "review"      # a paraphrase
    assert duplicate_band(model.similarity(text("FB-001"), text("FB-004"))) == "new"         # other language


def test_a_repost_is_linked_and_closed_automatically(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("Critical", 0.84))

    async def run():
        first = (await pipeline.create_ticket(feedback_id="FB-001"))["ticket_id"]
        second = (await pipeline.create_ticket(feedback_id="FB-002"))["ticket_id"]
        await pipeline.advance(second)
        return first, await pipeline.advance(second)

    first, linked = asyncio.run(run())
    assert linked["status"] == "duplicate" and linked["duplicate_of"] == first
    assert [stage["status"] for stage in linked["stages"]][2:] == ["skipped"] * 7


def test_a_possible_duplicate_waits_for_a_person(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("Low", 0.82), interpret=interpret_as_given)

    async def paused_pair():
        first = (await pipeline.create_ticket(feedback_id="FB-011"))["ticket_id"]
        second = (await pipeline.create_ticket(feedback_id="FB-012"))["ticket_id"]
        await pipeline.advance(second)
        return first, second, await pipeline.advance(second)

    first, second, paused = asyncio.run(paused_pair())
    assert paused["waiting_for"] == "duplicate_review"
    assert paused["pending_gate"]["evidence"]["cosine"] >= 0.70

    linked = asyncio.run(pipeline.review(second, "reviewer", True, "accept", "Same OTP problem"))
    assert linked["status"] == "duplicate" and linked["duplicate_of"] == first


def test_a_reviewer_can_keep_a_possible_duplicate_as_new(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("Low", 0.82), interpret=interpret_as_given)

    async def run():
        await pipeline.create_ticket(feedback_id="FB-011")
        second = (await pipeline.create_ticket(feedback_id="FB-012"))["ticket_id"]
        await pipeline.advance(second)
        await pipeline.advance(second)
        await pipeline.review(second, "reviewer", False, "request_changes", "Different account, keep it")
        return await pipeline.advance(second)

    kept = asyncio.run(run())
    assert kept["agent_outputs"]["triage"]["duplicate"]["band"] == "new"
    assert kept["current_stage"] == "assignment" and kept["duplicate_of"] is None  # Low passes the autonomy gate
