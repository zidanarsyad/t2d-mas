"""Ticket deduplication and severity triage components."""

from .gate import GateDecision, evaluate_gate

__all__ = ["GateDecision", "evaluate_gate"]
