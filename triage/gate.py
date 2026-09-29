"""Autonomy gate shared by ticket triage decisions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


RISK_BY_CLASS: dict[str, float] = {
    "Low": 0.1,
    "Medium": 0.3,
    "High": 0.6,
    "Critical": 1.0,
}


@dataclass(frozen=True)
class GateDecision:
    action: str
    autonomous: bool
    predicted_class: str
    confidence: float
    risk: float
    tau: float
    risk_max: float


def evaluate_gate(
    probabilities: Mapping[str, float | str],
    tau: float = 0.70,
    risk_max: float = 0.60,
    predicted_class: str | None = None,
) -> GateDecision:
    """Allow autonomy only when confidence and class risk both meet policy."""
    class_probabilities = {
        label: float(probabilities[label])
        for label in RISK_BY_CLASS
        if label in probabilities
    }
    if not class_probabilities:
        raise ValueError("probabilities must contain at least one class")
    if not 0 <= tau <= 1 or not 0 <= risk_max <= 1:
        raise ValueError("tau and risk_max must be between 0 and 1")
    label = predicted_class or max(class_probabilities, key=class_probabilities.__getitem__)
    if label not in class_probabilities:
        raise ValueError(f"Unknown or missing predicted class: {label}")
    confidence = class_probabilities[label]
    if not 0 <= confidence <= 1:
        raise ValueError("class probability must be between 0 and 1")
    risk = RISK_BY_CLASS[label]
    autonomous = confidence >= tau and risk <= risk_max
    return GateDecision(
        action="autonomous" if autonomous else "escalate",
        autonomous=autonomous,
        predicted_class=label,
        confidence=confidence,
        risk=risk,
        tau=tau,
        risk_max=risk_max,
    )
