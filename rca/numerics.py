"""Small deterministic reference calculation for the report's GraphSAGE example."""
from __future__ import annotations

import numpy as np


def reference_mean_sage_scores(
    features: list[list[float]],
    directed_edges: list[tuple[int, int]],
    weight: list[list[float]],
    readout: list[float],
) -> list[float]:
    """One hand-configured mean-aggregator pass used to verify the numeric fixture.

    For this reference calculation the directed chain supplies neighborhood context
    to both endpoints. The actual PyG model learns its two weighted layers from data.
    """
    x = np.asarray(features, dtype=np.float64)
    w = np.asarray(weight, dtype=np.float64)
    r = np.asarray(readout, dtype=np.float64)
    neighbors = [set() for _ in range(len(x))]
    for source, target in directed_edges:
        neighbors[source].add(target)
        neighbors[target].add(source)
    result = []
    for index, adjacent in enumerate(neighbors):
        neighbor_mean = x[list(sorted(adjacent))].mean(axis=0) if adjacent else np.zeros(x.shape[1])
        aggregate = x[index] + neighbor_mean
        result.append(float((w @ aggregate) @ r))
    return result
