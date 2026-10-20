"""Broker-Triage's local rules (English and Indonesian) and its optional OpenRouter call."""
import asyncio

from agents import feedback_samples, severity_triage
from agents.severity_triage import classify_ticket, classify_ticket_with_llm


def test_checkout_outage_is_classified_as_high_impact():
    result = classify_ticket("Checkout outage during the sale")
    assert result["severity"] == "High"
    assert "outage" in result["matched_cues"]


def test_casual_indonesian_is_understood_after_slang_normalization():
    assert classify_ticket("OTP gak masuk2, gabisa login sama sekali")["severity"] == "High"
    critical = classify_ticket("saldo GoPay kepotong tapi pesanan nggak muncul")
    assert critical["severity"] == "Critical" and "terpotong tapi" in critical["matched_cues"]
    assert classify_ticket("Ada typo di halaman checkout")["severity"] == "Low"


def test_rules_match_the_hand_labelled_feedback_corpus():
    # The corpus was written for this demo, so this checks the rules stay consistent with it.
    misses = [sample.feedback_id for sample in feedback_samples.SAMPLES
              if classify_ticket(f"{sample.title or ''}\n{sample.text}")["severity"] != sample.expected_severity]
    assert misses == []


def test_explicit_reviewer_severity_correction_applies_without_openrouter():
    result = asyncio.run(classify_ticket_with_llm(
        "Seller payout issue with unclear impact",
        review_feedback={"summary": "The reviewer knows sellers are affected.",
                         "requested_changes": ["This should be Critical since it can affect sellers."]}))
    assert result["severity"] == "Critical" and result["reviewer_override"] == "Critical"
    assert result["provider"] == "rules_fallback"
    assert result["fallback_reason"] == "OPENROUTER_API_KEY is unset"


def test_openrouter_uses_qwen_first_and_ling_as_model_fallback(monkeypatch):
    request_body = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"model": "inclusionai/ling-3.0-flash-sante:free",
                    "choices": [{"message": {"content":
                        '{"severity":"High","category":"seller impact","rationale":"Seller transactions may fail."}'}}]}

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, headers, json):
            request_body.update(json)
            assert headers["Authorization"] == "Bearer test-key"
            return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(severity_triage.httpx, "AsyncClient", Client)

    result = asyncio.run(severity_triage.classify_ticket_with_llm("Seller payments are failing."))

    assert request_body["models"] == ["qwen/qwen3.8-27b:free", "inclusionai/ling-3.0-flash-sante:free"]
    assert request_body["max_tokens"] == 512 and "response_format" not in request_body
    assert result["model"] == "inclusionai/ling-3.0-flash-sante:free"
    assert result["confidence"] <= 0.69  # model answers always go to a person
    assert result["fallback_used"] is True
