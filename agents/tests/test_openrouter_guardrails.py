"""OpenRouter guardrails: a rate limit never skips the autonomy gate, and only free models are sent."""
import asyncio
import json

import httpx
import pytest

from agents import app as api
from agents import severity_triage
from agents.app import ManualReview, ManualTicket
from agents.audit import MemoryAuditSink
from agents.orchestrator import T2DOrchestrator

FREE_MODELS = [default for _variable, default in severity_triage._DEFAULT_MODELS]
RATE_LIMITED = (429, {"error": {"code": 429, "message": "Rate limit exceeded: free-models-per-min"}})


def proposal(severity):
    """A successful OpenRouter chat completion that proposes `severity`."""
    content = json.dumps({"severity": severity, "category": "checkout", "rationale": "Test proposal."})
    return 200, {"model": FREE_MODELS[0], "choices": [{"message": {"content": content}}]}


@pytest.fixture
def sandbox(monkeypatch):
    """Run the manual sandbox in memory, with an OpenRouter key and default model settings."""
    audit = MemoryAuditSink()

    class Bus:
        async def publish(self, _message):
            return "guardrail-1"

    async def no_event(_event):
        return None

    monkeypatch.setattr(api.app.state, "audit", audit, raising=False)
    monkeypatch.setattr(api.app.state, "pipeline", T2DOrchestrator(audit), raising=False)
    monkeypatch.setattr(api.app.state, "manual_ticket_records", {}, raising=False)
    monkeypatch.setattr(api.app.state, "bus", Bus(), raising=False)
    monkeypatch.setattr(api, "_save_ticket_record", lambda *_args: None)
    monkeypatch.setattr(api, "_update_ticket_severity", lambda *_args: None)
    monkeypatch.setattr(api.event_hub, "publish", no_event)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_FALLBACK_MODEL", raising=False)
    return audit


def fake_openrouter(monkeypatch, *answers):
    """Answer OpenRouter requests locally, in order (the last answer repeats).

    Returns the list of request bodies that were sent.
    """
    sent = []
    real_client = httpx.AsyncClient

    def handler(request):
        sent.append(json.loads(request.content))
        status_code, payload = answers[min(len(sent), len(answers)) - 1]
        return httpx.Response(status_code, json=payload)

    monkeypatch.setattr(httpx, "AsyncClient",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    return sent


@pytest.mark.parametrize(("title", "body", "severity", "reason"), [
    # Rules are confident (0.91), but Critical risk (1.0) is above R_max.
    ("Customer data breach", "Exposed customer data after unauthorized access to the admin API.",
     "Critical", "risk_too_high"),
    # Rules give High a confidence of 0.68, below tau.
    ("Checkout outage", "Customers cannot complete checkout during a sale.", "High", "low_confidence"),
])
def test_rate_limited_triage_still_escalates_to_a_human(sandbox, monkeypatch, title, body, severity, reason):
    fake_openrouter(monkeypatch, RATE_LIMITED)

    async def run():
        ticket = await api.start_manual_ticket(ManualTicket(title=title, body=body))
        await api.advance_manual_ticket(ticket["ticket_id"])  # intake -> triage
        return await api.advance_manual_ticket(ticket["ticket_id"])  # autonomy gate

    paused = asyncio.run(run())
    assert paused["severity"] == severity
    assert paused["status"] == "waiting_for_review"
    assert paused["waiting_for"] == "autonomy_gate"
    assert paused["current_stage"] == "triage"
    gate = next(event for event in sandbox.events if event.action == "policy_gate")
    assert gate.decision == "escalated"
    assert gate.details["reason"] == reason
    assert gate.details["rate_limited"] is True
    assert gate.details["fallback_reason"] == "OpenRouter returned HTTP 429"


def test_rate_limited_change_request_waits_for_clarification(sandbox, monkeypatch):
    # The first triage succeeds and escalates; only the reviewer's re-triage hits the rate limit.
    fake_openrouter(monkeypatch, proposal("High"), RATE_LIMITED)

    async def run():
        ticket = await api.start_manual_ticket(ManualTicket(
            title="Checkout outage", body="Customers cannot complete checkout during a sale."))
        await api.advance_manual_ticket(ticket["ticket_id"])
        await api.advance_manual_ticket(ticket["ticket_id"])
        return await api.review_manual_ticket(ticket["ticket_id"], ManualReview(
            approver="reviewer", approved=False, intent="request_changes",
            reason="Only one region is affected; please reassess the impact."))

    result = asyncio.run(run())
    review = result["reviews"][-1]
    assert review["decision"] == "clarification_requested"
    assert "HTTP 429" in review["interpretation"]["clarification_question"]
    assert result["status"] == "waiting_for_review"
    assert result["waiting_for"] == "autonomy_gate"


def test_model_ids_without_free_suffix_are_never_sent(sandbox, monkeypatch):
    paid = {"OPENROUTER_MODEL": "openai/gpt-4o", "OPENROUTER_FALLBACK_MODEL": "anthropic/claude-sonnet-4.5"}
    for variable, model in paid.items():
        monkeypatch.setenv(variable, model)
    sent = fake_openrouter(monkeypatch, proposal("Low"))

    async def run():
        await api.start_manual_ticket(ManualTicket(
            title="Checkout label typo", body="The checkout button label has a typo."))
        return await severity_triage.interpret_review_feedback("Also check the mobile layout.", "qa")

    interpretation = asyncio.run(run())
    # Triage and review interpretation each made one request, with the default free models only.
    assert [body["models"] for body in sent] == [FREE_MODELS, FREE_MODELS]
    assert not any(model in json.dumps(sent) for model in paid.values())
    triage = next(event.details["output"] for event in sandbox.events
                  if event.action == "agent_output" and event.details["stage"] == "triage")
    assert triage["provider"] == "openrouter"
    for recorded in (triage["model_fallback_reason"], interpretation["model_fallback_reason"]):
        assert "OPENROUTER_MODEL=openai/gpt-4o is not a ':free' model" in recorded
        assert "OPENROUTER_FALLBACK_MODEL=anthropic/claude-sonnet-4.5 is not a ':free' model" in recorded


def test_a_configured_free_model_is_kept_when_the_other_setting_is_paid(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODEL", "openai/gpt-4o")

    models, reason = severity_triage._openrouter_models()

    assert models == ["meta-llama/llama-3.3-70b-instruct:free", FREE_MODELS[1]]
    assert reason == (f"OPENROUTER_FALLBACK_MODEL=openai/gpt-4o is not a ':free' model; "
                      f"used {FREE_MODELS[1]} instead")
