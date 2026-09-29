"""Small metric implementations used by the four-arm evaluation."""
from __future__ import annotations

from collections.abc import Iterable, Sequence


def recall_at_k(relevant: Iterable[str], ranked: Sequence[str], k: int) -> float:
    """Fraction of relevant items retrieved in the first k ranked results."""
    truth = set(relevant)
    return 0.0 if not truth else len(truth.intersection(ranked[:k])) / len(truth)


def average_precision(relevant: Iterable[str], ranked: Sequence[str]) -> float:
    """Average precision for one ranked list; missing relevant items count as zero."""
    truth = set(relevant)
    if not truth:
        return 0.0
    hits = 0
    total = 0.0
    seen: set[str] = set()
    for rank, item in enumerate(ranked, start=1):
        # Duplicate retrievals must not add extra hits or inflate average precision.
        if item in seen:
            continue
        seen.add(item)
        if item in truth:
            hits += 1
            total += hits / rank
    return total / len(truth)


def mean_average_precision(relevant_sets: Iterable[Iterable[str]],
                           ranked_lists: Iterable[Sequence[str]]) -> float:
    """Mean average precision over query-aligned relevance sets and rankings."""
    pairs = [(set(relevant), ranked)
             for relevant, ranked in zip(relevant_sets, ranked_lists, strict=True)]
    # Queries without any labeled relevant document have undefined AP and are excluded.
    values = [average_precision(relevant, ranked) for relevant, ranked in pairs if set(relevant)]
    return sum(values) / len(values) if values else 0.0


def macro_f1(actual: Sequence[str], predicted: Sequence[str],
             labels: Sequence[str]) -> float:
    """Unweighted mean F1 across labels, assigning zero to undefined class scores."""
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have equal lengths")
    scores = []
    for label in labels:
        tp = sum(a == label and p == label for a, p in zip(actual, predicted))
        fp = sum(a != label and p == label for a, p in zip(actual, predicted))
        fn = sum(a == label and p != label for a, p in zip(actual, predicted))
        denom = 2 * tp + fp + fn
        scores.append(0.0 if denom == 0 else 2 * tp / denom)
    return sum(scores) / len(scores) if scores else 0.0


def napfd(detected_fault_ranks: Iterable[int], num_tests: int,
          total_faults: int) -> float:
    """Budget-aware NAPFD using one-based ranks in the test order."""
    if num_tests < 1 or total_faults < 0:
        raise ValueError("num_tests must be positive and total_faults non-negative")
    if total_faults == 0:
        return 1.0
    ranks = list(detected_fault_ranks)
    if any(rank < 1 or rank > num_tests for rank in ranks):
        raise ValueError("fault ranks must be between 1 and num_tests")
    detected = min(len(ranks), total_faults) / total_faults
    value = detected - sum(ranks) / (num_tests * total_faults) + detected / (2 * num_tests)
    return max(0.0, min(1.0, value))


def rca_top_k(ranked_nodes: Sequence[str | int], incident_nodes: Iterable[str | int],
              k: int) -> float:
    """Return 1 when an incident node appears in the first k positions, else 0."""
    truth = set(incident_nodes)
    return float(bool(truth.intersection(ranked_nodes[:k])))


def dora_metrics(*, successful_deployments: int, total_days: float,
                 lead_times_hours: Sequence[float], recovery_times_hours: Sequence[float],
                 failed_deployments: int, total_deployments: int,
                 reworked_changes: int, total_changes: int) -> dict[str, float]:
    """Compute five classroom DORA-style aggregates from supplied event records."""
    if total_days <= 0:
        raise ValueError("total_days must be positive")
    return {
        "deployment_frequency_per_day": successful_deployments / total_days,
        "lead_time_hours_mean": _mean(lead_times_hours),
        "failed_deployment_recovery_hours_mean": _mean(recovery_times_hours),
        "change_failure_rate": failed_deployments / total_deployments if total_deployments else 0.0,
        "rework_rate": reworked_changes / total_changes if total_changes else 0.0,
    }


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
