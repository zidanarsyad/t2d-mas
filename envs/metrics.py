"""Reward and reporting metrics shared by the environments and evaluators."""
from __future__ import annotations

from collections.abc import Iterable


def napfd(detected_fault_ranks: Iterable[int], num_tests: int,
          total_faults: int) -> float:
    """Budget-aware NAPFD; ranks are 1-based positions in the full priority order."""
    if num_tests < 1:
        raise ValueError("num_tests must be positive")
    if total_faults <= 0:
        return 1.0
    ranks = list(detected_fault_ranks)
    if any(rank < 1 or rank > num_tests for rank in ranks):
        raise ValueError("fault ranks must be between 1 and num_tests")
    detected_fraction = min(len(ranks), total_faults) / total_faults
    score = detected_fraction - sum(ranks) / (num_tests * total_faults)
    score += detected_fraction / (2 * num_tests)
    return float(max(0.0, min(1.0, score)))


def prioritization_reward(napfd_value: float, total_execution_seconds: float,
                          lambda_time: float) -> float:
    """R = NAPFD - lambda_time * total test execution seconds."""
    return float(napfd_value - lambda_time * total_execution_seconds)


def deployment_outcome_reward(rollback: bool, hours_delayed: float = 0.0) -> float:
    """R = +1 for SLO success or -5 for rollback, minus 0.2 per delay hour."""
    base = -5.0 if rollback else 1.0
    return base - 0.2 * hours_delayed
