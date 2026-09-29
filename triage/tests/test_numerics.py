"""Reproducible numerical examples from the project report."""
import numpy as np
import pytest

from triage.dedup import decision_for_score, DedupAction
from triage.severity import SEVERITY_CLASSES, softmax_probabilities


def cosine(a: list[float], b: list[float]) -> float:
    left = np.asarray(a, dtype=np.float64)
    right = np.asarray(b, dtype=np.float64)
    return float(np.dot(left, right) / (np.linalg.norm(left) * np.linalg.norm(right)))


def test_report_duplicate_cosines() -> None:
    ticket_a = [0.80, 0.10, 0.00, 0.30, 0.20]
    ticket_b = [0.75, 0.15, 0.00, 0.35, 0.25]
    ticket_c = [0.10, 0.00, 0.90, 0.05, 0.00]
    assert cosine(ticket_a, ticket_b) == pytest.approx(0.994, abs=1e-3)
    assert cosine(ticket_a, ticket_c) == pytest.approx(0.119, abs=1e-3)


def test_report_softmax_probability() -> None:
    probabilities = softmax_probabilities([1.2, 0.5, 2.1, 0.3])
    assert tuple(SEVERITY_CLASSES) == ("Low", "Medium", "High", "Critical")
    assert probabilities[2] == pytest.approx(0.564, abs=1e-3)
    assert float(probabilities.sum()) == pytest.approx(1.0)


def test_duplicate_score_zones() -> None:
    assert decision_for_score(0.85) is DedupAction.AUTO_LINK
    assert decision_for_score(0.70) is DedupAction.HUMAN_REVIEW
    assert decision_for_score(0.699) is DedupAction.NEW_TICKET

