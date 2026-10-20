"""Reward and reporting metrics shared by the environments and evaluators."""
from __future__ import annotations

# NAPFD is defined once, in eval/metrics.py, and shared with the CI environment.
from eval.metrics import napfd  # noqa: F401  (re-exported for envs.test_prioritization)


def prioritization_reward(napfd_value: float, total_execution_seconds: float,
                          lambda_time: float) -> float:
    """R = NAPFD - lambda_time * total test execution seconds."""
    return float(napfd_value - lambda_time * total_execution_seconds)


def deployment_outcome_reward(rollback: bool, hours_delayed: float = 0.0) -> float:
    """R = +1 for SLO success or -5 for rollback, minus 0.2 per delay hour."""
    base = -5.0 if rollback else 1.0
    return base - 0.2 * hours_delayed
