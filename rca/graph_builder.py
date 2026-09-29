"""Build directed service-call graphs with seven-day standardized features."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import numpy as np
import torch


FEATURES = ("latency", "error_rate", "cpu", "mem", "saturation")


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def compute_7d_baselines(
    history: Iterable[dict[str, Any]],
    as_of: datetime | None = None,
    window_days: int = 7,
) -> dict[str, dict[str, tuple[float, float]]]:
    """Compute per-instance population mean/std using only the preceding 7 days."""
    end = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = end - timedelta(days=window_days)
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in history:
        timestamp = _as_datetime(row["timestamp"])
        if not start <= timestamp <= end:
            continue
        instance = str(row["service_instance_id"])
        for metric in FEATURES:
            grouped[instance][metric].append(float(row[metric]))
    baseline: dict[str, dict[str, tuple[float, float]]] = {}
    for instance, metric_values in grouped.items():
        baseline[instance] = {}
        for metric, values in metric_values.items():
            baseline[instance][metric] = (float(np.mean(values)), float(np.std(values)))
    if not baseline:
        raise ValueError("No baseline observations found inside the requested time window")
    return baseline


def build_service_graph(
    service_metrics: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    baseline: dict[str, dict[str, tuple[float, float]]],
    epsilon: float = 1e-8,
):
    """Return a PyG Data graph. Calls are directed caller->callee; volume is edge_weight.

    Metric records require ``service_instance_id`` and the five values in ``FEATURES``.
    ``baseline`` is produced by :func:`compute_7d_baselines` and keyed by instance ID.
    """
    try:
        from torch_geometric.data import Data
    except ImportError as exc:
        raise RuntimeError("Install rca/requirements.txt to build PyG graphs") from exc
    if not service_metrics:
        raise ValueError("service_metrics cannot be empty")

    node_ids = [str(row["service_instance_id"]) for row in service_metrics]
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("service_instance_id values must be unique per graph")
    node_index = {instance: index for index, instance in enumerate(node_ids)}
    feature_rows = []
    for row, instance in zip(service_metrics, node_ids):
        if instance not in baseline:
            raise ValueError(f"No seven-day baseline for service instance {instance!r}")
        z_values = []
        for metric in FEATURES:
            mean, std = baseline[instance][metric]
            # A constant baseline has no reliable scale; treat it as no deviation.
            z_values.append(0.0 if abs(std) < epsilon else (float(row[metric]) - mean) / std)
        feature_rows.append(z_values)

    # Coalesce repeated spans so the edge weight is total request volume.
    volumes: dict[tuple[int, int], float] = defaultdict(float)
    for call in calls:
        caller, callee = str(call["caller"]), str(call["callee"])
        if caller not in node_index or callee not in node_index:
            raise ValueError(f"Call references an unknown service: {caller!r}->{callee!r}")
        volume = float(call.get("request_count", call.get("volume", 1.0)))
        if volume < 0:
            raise ValueError("request volume must be non-negative")
        volumes[(node_index[caller], node_index[callee])] += volume
    ordered_edges = sorted(volumes)
    edge_index = (torch.tensor(ordered_edges, dtype=torch.long).t().contiguous()
                  if ordered_edges else torch.empty((2, 0), dtype=torch.long))
    edge_weight = torch.tensor([volumes[edge] for edge in ordered_edges], dtype=torch.float32)

    # The call graph stays directed. A second, bidirectional view lets the scorer
    # share anomaly context with both callers and callees without losing direction.
    reverse_edges = edge_index.flip(0)
    message_edge_index = torch.cat([edge_index, reverse_edges], dim=1)
    message_edge_weight = torch.cat([edge_weight, edge_weight], dim=0)
    return Data(
        x=torch.tensor(feature_rows, dtype=torch.float32),
        edge_index=edge_index,
        edge_weight=edge_weight,
        message_edge_index=message_edge_index,
        message_edge_weight=message_edge_weight,
        node_ids=node_ids,
    )
