"""Paired and multi-arm statistics for the seed-level measurements."""
from __future__ import annotations

from itertools import combinations
from math import sqrt
from typing import Sequence

import numpy as np
from scipy.stats import friedmanchisquare, studentized_range, wilcoxon


def wilcoxon_signed_rank(left: Sequence[float], right: Sequence[float]) -> dict[str, float]:
    """Wilcoxon signed-rank test for paired observations; ties are handled by SciPy."""
    if len(left) != len(right) or not left:
        raise ValueError("paired samples must have equal, non-zero lengths")
    if all(a == b for a, b in zip(left, right, strict=True)):
        return {"statistic": 0.0, "p_value": 1.0}
    result = wilcoxon(left, right, alternative="two-sided", method="auto")
    return {"statistic": float(result.statistic), "p_value": float(result.pvalue)}


def cliffs_delta(left: Sequence[float], right: Sequence[float]) -> float:
    """Nonparametric effect size: P(left > right) - P(left < right)."""
    if not left or not right:
        raise ValueError("samples must be non-empty")
    greater = sum(a > b for a in left for b in right)
    less = sum(a < b for a in left for b in right)
    return (greater - less) / (len(left) * len(right))


def holm_bonferroni(p_values: Sequence[float]) -> list[float]:
    """Return Holm-adjusted p-values in the original input order."""
    count = len(p_values)
    order = sorted(range(count), key=p_values.__getitem__)
    adjusted = [0.0] * count
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (count - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted


def friedman_nemenyi(arm_values: dict[str, Sequence[float]]) -> tuple[dict[str, float], list[dict[str, float | str]]]:
    """Friedman omnibus test and Nemenyi pairwise tests over paired seed blocks."""
    arms = list(arm_values)
    if len(arms) < 3 or len({len(arm_values[name]) for name in arms}) != 1:
        raise ValueError("Friedman requires at least three equally sized paired arms")
    matrix = np.asarray([arm_values[name] for name in arms], dtype=float).T
    omnibus = friedmanchisquare(*(matrix[:, index] for index in range(matrix.shape[1])))
    # Average ranks are the Nemenyi input; low values rank first for minimized metrics.
    ranks = np.argsort(np.argsort(matrix, axis=1, kind="stable"), axis=1, kind="stable") + 1
    mean_ranks = ranks.mean(axis=0)
    n_blocks, n_arms = matrix.shape
    pairs: list[dict[str, float | str]] = []
    for left, right in combinations(range(n_arms), 2):
        q = abs(mean_ranks[left] - mean_ranks[right]) / sqrt(n_arms * (n_arms + 1) / (6 * n_blocks))
        p = float(studentized_range.sf(q * sqrt(2), n_arms, np.inf))
        pairs.append({"arm_a": arms[left], "arm_b": arms[right],
                      "mean_rank_a": float(mean_ranks[left]),
                      "mean_rank_b": float(mean_ranks[right]), "q": float(q), "p_value": p})
    corrected = holm_bonferroni([float(row["p_value"]) for row in pairs])
    for row, value in zip(pairs, corrected, strict=True):
        row["p_holm"] = value
    return {"statistic": float(omnibus.statistic), "p_value": float(omnibus.pvalue)}, pairs
