"""Security-Policy agent checks: signed bundles, result allowlists, secret scans and the autonomy gate."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from triage import gate as shared_gate

# One risk table for the whole project; the evaluation harness imports the same one.
RISK_BY_CLASS = shared_gate.RISK_BY_CLASS
SECRET_PATTERNS = (
    re.compile(r"""(?i)(api[_-]?key|(?:access[_-]?)?token|secret|password)\s*[:=]\s*['"]?[^\s'"]{8,}"""),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)

# Only aggregate fields may cross a production-node boundary.
DEFAULT_EGRESS_FIELDS = frozenset({
    "service", "latency_p50_ms", "latency_p95_ms", "error_rate",
    "cpu_z", "mem_z", "saturation_z", "request_count", "evidence_hash",
})


class SecurityError(ValueError):
    """Raised when a bundle or its output violates a security check."""


def scan_for_secrets(value: Any) -> bool:
    """Return True if a string representation contains a likely secret."""
    return any(pattern.search(str(value)) for pattern in SECRET_PATTERNS)


def find_secrets(text: str) -> list[str]:
    """Return a short, redacted description of each secret-like match (for review evidence)."""
    findings = []
    for line_number, line in enumerate(str(text).splitlines(), start=1):
        for pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(f"line {line_number}: {match.group(0)[:12]}… (redacted)")
                break
    return findings


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
    """Apply P >= tau AND risk <= risk_max; otherwise require human review.

    The rule itself lives in triage/gate.py so the live agents and the evaluation
    harness share one implementation; this wrapper keeps the simpler signature.
    """
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    if risk_class not in RISK_BY_CLASS:
        raise ValueError(f"unknown risk class: {risk_class}")
    shared = shared_gate.evaluate_gate({risk_class: probability}, tau=tau, risk_max=risk_max)
    reason = "autonomous" if shared.autonomous else ("low_confidence" if probability < tau else "risk_too_high")
    return GateDecision(shared.autonomous, reason, shared.risk)
