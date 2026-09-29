"""Top-k and reciprocal-rank evaluation for incident-node rankings."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np


def ranking_metrics(scores: Iterable[float], incident_nodes: Iterable[int]) -> dict[str, float]:
    """Return per-graph Top-1, Top-3, and reciprocal rank (zero-based node IDs)."""
    values = np.asarray(list(scores), dtype=float)
    positives = set(int(index) for index in incident_nodes)
    if values.size == 0 or not positives:
        raise ValueError("scores and incident_nodes must be non-empty")
    order = np.argsort(-values, kind="stable")
    ranks = [rank for rank, node_id in enumerate(order, start=1) if int(node_id) in positives]
    first_rank = min(ranks) if ranks else None
    return {
        "top1_accuracy": float(first_rank == 1),
        "top3_accuracy": float(first_rank is not None and first_rank <= 3),
        "mrr": 0.0 if first_rank is None else 1.0 / first_rank,
    }


def evaluate_dataset(model: Any, examples: Iterable[tuple[Any, list[int]]]) -> dict[str, float]:
    """Average ranking metrics over graphs; examples are graph/incident-index pairs."""
    import torch
    results = []
    model.eval()
    with torch.no_grad():
        for graph, incident_nodes in examples:
            edge_index = getattr(graph, "message_edge_index", graph.edge_index)
            edge_weight = getattr(graph, "message_edge_weight", graph.edge_weight)
            scores = model(graph.x, edge_index, edge_weight).detach().cpu().numpy()
            results.append(ranking_metrics(scores, incident_nodes))
    if not results:
        raise ValueError("Evaluation examples cannot be empty")
    return {key: float(np.mean([row[key] for row in results])) for key in results[0]}
