import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agents.mobility import AgentBundle, should_migrate
from agents.security_policy import (SecurityError, evaluate_gate, sign_bundle,
                                    validate_egress, verify_bundle_signature)


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
