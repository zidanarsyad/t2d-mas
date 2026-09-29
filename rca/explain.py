"""GNNExplainer summaries for the top suspicious services in a graph."""
from __future__ import annotations

from typing import Any

import torch


def explain_top3_nodes(model: Any, graph: Any, target_node: int,
                       epochs: int = 100) -> dict[str, Any]:
    """Explain one target score and return its top three explanatory graph nodes."""
    try:
        from torch_geometric.explain import Explainer, GNNExplainer
    except ImportError as exc:
        raise RuntimeError("Install rca/requirements.txt to use GNNExplainer") from exc
    if not 0 <= target_node < len(graph.node_ids):
        raise IndexError("target_node is outside this graph")
    edge_index = getattr(graph, "message_edge_index", graph.edge_index)
    edge_weight = getattr(graph, "message_edge_weight", graph.edge_weight)
    model.eval()
    explainer = Explainer(
        model=model,
        algorithm=GNNExplainer(epochs=epochs),
        explanation_type="model",
        node_mask_type="attributes",
        edge_mask_type="object",
        model_config={"mode": "regression", "task_level": "node", "return_type": "raw"},
    )
    with torch.no_grad():
        target_scores = model(graph.x, edge_index, edge_weight).detach()
    explanation = explainer(
        x=graph.x,
        edge_index=edge_index,
        edge_weight=edge_weight,
        target=target_scores,
        index=target_node,
    )
    importance = torch.zeros(len(graph.node_ids), dtype=graph.x.dtype, device=graph.x.device)
    if explanation.node_mask is not None:
        node_mask = explanation.node_mask
        importance += node_mask.abs().sum(dim=-1).to(importance.device)
    edge_mask = explanation.edge_mask
    if edge_mask is not None:
        for edge_id, (source, target) in enumerate(edge_index.t().tolist()):
            value = edge_mask[edge_id].to(importance.device)
            importance[source] += value
            importance[target] += value
    limit = min(3, len(graph.node_ids))
    ranked = torch.argsort(importance, descending=True, stable=True)[:limit].tolist()
    predicted_scores = target_scores.detach().cpu().tolist()
    nodes = [{"service_instance_id": graph.node_ids[index],
              "importance": float(importance[index].detach().cpu()),
              "suspicion_score": float(predicted_scores[index])}
             for index in ranked]
    selected = set(ranked)
    edges = []
    if edge_mask is not None:
        for edge_id, (source, target) in enumerate(edge_index.t().tolist()):
            if source in selected and target in selected:
                edges.append({"source": graph.node_ids[source], "target": graph.node_ids[target],
                              "importance": float(edge_mask[edge_id].detach().cpu())})
    return {"target_node": graph.node_ids[target_node], "nodes": nodes, "edges": edges}
