"""Two-layer, request-volume-weighted GraphSAGE node ranker."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import torch
from torch import nn
from torch.nn import functional as F

try:
    from torch_geometric.nn import MessagePassing
except ImportError:  # Keep pure numeric helpers importable before optional PyG install.
    MessagePassing = None


if MessagePassing is not None:
    class WeightedSAGEConv(MessagePassing):
        """SAGE mean aggregator that uses request volume as a weighted mean."""

        def __init__(self, in_channels: int, out_channels: int) -> None:
            super().__init__(aggr="add", flow="source_to_target")
            self.lin_root = nn.Linear(in_channels, out_channels, bias=True)
            self.lin_neigh = nn.Linear(in_channels, out_channels, bias=False)

        def forward(self, x: torch.Tensor, edge_index: torch.Tensor,
                    edge_weight: torch.Tensor | None = None) -> torch.Tensor:
            if edge_weight is None:
                edge_weight = x.new_ones(edge_index.size(1))
            # The same weighted messages define both the numerator and denominator.
            neighbor_sum = self.propagate(edge_index, x=x, edge_weight=edge_weight)
            degree = x.new_zeros(x.size(0)).index_add_(0, edge_index[1], edge_weight)
            neighbor_mean = neighbor_sum / degree.clamp_min(1e-12).unsqueeze(-1)
            neighbor_mean = torch.where(degree.unsqueeze(-1) > 0, neighbor_mean,
                                        torch.zeros_like(neighbor_mean))
            return self.lin_root(x) + self.lin_neigh(neighbor_mean)

        def message(self, x_j: torch.Tensor, edge_weight: torch.Tensor) -> torch.Tensor:
            return x_j * edge_weight.unsqueeze(-1)
else:
    class WeightedSAGEConv(nn.Module):
        """Dependency error raised only when a PyG model is actually constructed."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            super().__init__()
            raise RuntimeError("Install rca/requirements.txt to use the GraphSAGE model")


class GraphSAGEScorer(nn.Module):
    """Two GraphSAGE layers followed by a scalar suspiciousness readout."""

    def __init__(self, in_channels: int = 5, hidden_channels: int = 32,
                 dropout: float = 0.1) -> None:
        super().__init__()
        self.conv1 = WeightedSAGEConv(in_channels, hidden_channels)
        self.conv2 = WeightedSAGEConv(hidden_channels, hidden_channels)
        self.readout = nn.Linear(hidden_channels, 1)
        self.dropout = dropout

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor,
                edge_weight: torch.Tensor | None = None) -> torch.Tensor:
        """Return one ranking score per node; higher values indicate more suspicion."""
        x = F.relu(self.conv1(x, edge_index, edge_weight))
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = F.relu(self.conv2(x, edge_index, edge_weight))
        return self.readout(x).squeeze(-1)


def margin_ranking_loss(scores: torch.Tensor, incident_nodes: Iterable[int],
                        margin: float = 1.0) -> torch.Tensor:
    """Rank historical incident nodes above non-incident nodes in the same graph."""
    positive = sorted(set(int(index) for index in incident_nodes))
    if not positive:
        raise ValueError("Each training graph needs at least one labeled incident node")
    positive_tensor = torch.tensor(positive, device=scores.device, dtype=torch.long)
    negative = torch.tensor([i for i in range(scores.numel()) if i not in positive],
                            device=scores.device, dtype=torch.long)
    if negative.numel() == 0:
        raise ValueError("Ranking loss needs at least one non-incident node")
    pos_scores = scores[positive_tensor].repeat_interleave(negative.numel())
    neg_scores = scores[negative].repeat(positive_tensor.numel())
    targets = torch.ones_like(pos_scores)
    return F.margin_ranking_loss(pos_scores, neg_scores, targets, margin=margin)


def train_ranker(model: GraphSAGEScorer,
                 examples: Iterable[tuple[Any, list[int]]],
                 epochs: int = 20, learning_rate: float = 1e-3,
                 margin: float = 1.0) -> GraphSAGEScorer:
    """Simple per-graph optimizer loop for an assignment-sized incident dataset.

    Each example is ``(PyG Data, [incident node indices])``. Builders provide a
    bidirectional ``message_edge_index`` to share anomaly context across a call.
    """
    dataset = list(examples)
    if not dataset:
        raise ValueError("Training examples cannot be empty")
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    model.train()
    for _epoch in range(epochs):
        for graph, incident_nodes in dataset:
            optimizer.zero_grad()
            edge_index = getattr(graph, "message_edge_index", graph.edge_index)
            edge_weight = getattr(graph, "message_edge_weight", graph.edge_weight)
            scores = model(graph.x, edge_index, edge_weight)
            loss = margin_ranking_loss(scores, incident_nodes, margin)
            loss.backward()
            optimizer.step()
    return model
