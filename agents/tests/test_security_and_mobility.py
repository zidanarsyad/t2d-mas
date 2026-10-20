import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agents.mobility import AgentBundle, should_migrate
from agents.security_policy import SecurityError, evaluate_gate, validate_egress, verify_bundle_signature


def test_ed25519_bundle_signature_round_trip():
    key = Ed25519PrivateKey.generate()
    bundle = AgentBundle.create("Scout-Log", "print('{}')", {"node": 1}, key)
    assert verify_bundle_signature(bundle.payload(), bundle.signature, key.public_key())
    assert not verify_bundle_signature(bundle.payload() + b"tamper", bundle.signature, key.public_key())


def test_egress_only_returns_aggregates_and_rejects_raw_logs():
    assert validate_egress({"service": "api", "request_count": 7})["request_count"] == 7
    with pytest.raises(SecurityError):
        validate_egress({"raw_log": "user@example.com"})
    with pytest.raises(SecurityError):
        validate_egress({"service": "api", "evidence_hash": "token=abcdef0123456789"})


def test_gate_and_migration_break_even_rule():
    assert evaluate_gate(0.88, "Critical").autonomous is False
    assert evaluate_gate(0.90, "High").autonomous is True
    assert should_migrate(1365, 12, 2)
    assert not should_migrate(30, 12, 2)


def test_gate_wrapper_matches_the_original_rule_everywhere():
    # The live gate now delegates to triage/gate.py; it must give the same answers as before.
    from agents.security_policy import DEFAULT_EGRESS_FIELDS, RISK_BY_CLASS
    for risk_class, risk in RISK_BY_CLASS.items():
        for step in range(101):
            probability = step / 100
            decision = evaluate_gate(probability, risk_class)
            expected = probability >= 0.70 and risk <= 0.60
            assert decision.autonomous is expected and decision.risk == risk
            assert decision.reason == ("autonomous" if expected else
                                       "low_confidence" if probability < 0.70 else "risk_too_high")
    assert len(DEFAULT_EGRESS_FIELDS) == 9
