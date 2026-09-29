"""Dependency-only PageRank baseline for comparison with learned RCA ranking."""
from __future__ import annotations

import numpy as np


def pagerank_scores(edge_index, edge_weight, num_nodes: int,
                    damping: float = 0.85, max_iter: int = 100,
                    tolerance: float = 1e-8) -> np.ndarray:
    """Compute weighted directed PageRank; source nodes send rank to callees."""
    if num_nodes < 1:
        raise ValueError("num_nodes must be positive")
    if not 0 <= damping < 1:
        raise ValueError("damping must be in [0, 1)")
    edges = np.asarray(edge_index, dtype=np.int64)
    if edges.size == 0:
        return np.full(num_nodes, 1.0 / num_nodes)
    edges = edges.reshape(2, -1)
    weights = np.ones(edges.shape[1]) if edge_weight is None else np.asarray(edge_weight, dtype=float)
    if np.any(weights < 0):
        raise ValueError("edge weights cannot be negative")
    outgoing = np.zeros(num_nodes, dtype=float)
    np.add.at(outgoing, edges[0], weights)
    rank = np.full(num_nodes, 1.0 / num_nodes)
    for _ in range(max_iter):
        next_rank = np.full(num_nodes, (1.0 - damping) / num_nodes)
        dangling_mass = rank[outgoing == 0].sum()
        next_rank += damping * dangling_mass / num_nodes
        for edge_id, (source, target) in enumerate(edges.T):
            if outgoing[source] > 0:
                next_rank[target] += damping * rank[source] * weights[edge_id] / outgoing[source]
        if np.linalg.norm(next_rank - rank, ord=1) < tolerance:
            rank = next_rank
            break
        rank = next_rank
    return rank
