"""Classroom security checks: signed bundles, result allowlists, and autonomy gate."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

RISK_BY_CLASS = {"Low": 0.1, "Medium": 0.3, "High": 0.6, "Critical": 1.0}
SECRET_PATTERNS = (
    re.compile(r"""(?i)(api[_-]?key|(?:access[_-]?)?token|secret|password)\s*[:=]\s*['"]?[^\s'"]{8,}"""),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)

# Only aggregate fields may cross a production-node boundary.
DEFAULT_EGRESS_FIELDS = frozenset({
    "service", "latency_p50_ms", "latency_p95_ms", "error_rate",
    "cpu_z", "mem_z", "saturation_z", "request_count", "latency_p95_ms", "evidence_hash",
})


class SecurityError(ValueError):
    """Raised when a bundle or its output violates a security check."""


def scan_for_secrets(value: Any) -> bool:
    """Return True if a string representation contains a likely secret."""
    return any(pattern.search(str(value)) for pattern in SECRET_PATTERNS)


def validate_egress(result: Mapping[str, Any], allowed_fields: frozenset[str] = DEFAULT_EGRESS_FIELDS) -> dict[str, Any]:
    """Reject raw or unexpected result fields instead of silently exporting them."""
    forbidden = set(result) - set(allowed_fields)
    if forbidden:
        raise SecurityError(f"egress contains disallowed fields: {sorted(forbidden)}")
    if scan_for_secrets(result):
        raise SecurityError("secret-like value found in node result")
    return dict(result)


def sign_bundle(payload: bytes, private_key: Any) -> str:
    """Sign bytes with an Ed25519 private key and return a tagged base64 signature."""
    import base64
    return "ed25519:" + base64.b64encode(private_key.sign(payload)).decode("ascii")


def verify_bundle_signature(payload: bytes, signature: str, public_key: Any) -> bool:
    """Verify a tagged Ed25519 signature. Invalid signatures return False."""
    import base64
    from cryptography.exceptions import InvalidSignature
    if not signature.startswith("ed25519:"):
        return False
    try:
        public_key.verify(base64.b64decode(signature.split(":", 1)[1], validate=True), payload)
        return True
    except (InvalidSignature, ValueError):
        return False


@dataclass(frozen=True)
class GateDecision:
    autonomous: bool
    reason: str
    risk: float


def evaluate_gate(probability: float, risk_class: str, tau: float = 0.70, risk_max: float = 0.60) -> GateDecision:
    """Apply P >= tau AND risk <= risk_max; otherwise require human review."""
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    if risk_class not in RISK_BY_CLASS:
        raise ValueError(f"unknown risk class: {risk_class}")
    risk = RISK_BY_CLASS[risk_class]
    passed = probability >= tau and risk <= risk_max
    reason = "autonomous" if passed else ("low_confidence" if probability < tau else "risk_too_high")
    return GateDecision(passed, reason, risk)
