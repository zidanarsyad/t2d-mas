"""Seeded synthetic incident graphs for repeatable course experiments."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from .graph_builder import FEATURES, build_service_graph, compute_7d_baselines


def generate_synthetic_incidents(
    num_cases: int = 30,
    num_services: int = 6,
    seed: int = 42,
) -> list[tuple[object, list[int]]]:
    """Return ``(PyG graph, [failed node index])`` examples with known injected faults."""
    if num_cases < 1 or num_services < 2:
        raise ValueError("num_cases must be positive and num_services must be at least 2")
    rng = np.random.default_rng(seed)
    service_ids = [f"service-{index}" for index in range(num_services)]
    means = {
        "latency": 100.0, "error_rate": 0.02, "cpu": 40.0,
        "mem": 50.0, "saturation": 0.45,
    }
    stds = {
        "latency": 12.0, "error_rate": 0.006, "cpu": 6.0,
        "mem": 7.0, "saturation": 0.08,
    }
    as_of = datetime(2026, 1, 8, tzinfo=timezone.utc)
    history = []
    for service_index, instance in enumerate(service_ids):
        for tick in range(28):
            row = {"service_instance_id": instance,
                   "timestamp": as_of - timedelta(hours=6 * tick)}
            for metric in FEATURES:
                # Small deterministic offsets keep service baselines distinct.
                value = means[metric] + service_index * stds[metric] * 0.15
                value += rng.normal(0, stds[metric])
                row[metric] = max(0.0001, float(value))
            history.append(row)
    baseline = compute_7d_baselines(history, as_of=as_of)
    calls = [{"caller": service_ids[index], "callee": service_ids[index + 1],
              "request_count": int(rng.integers(20, 101))}
             for index in range(num_services - 1)]
    injection = {"latency": 3.0, "error_rate": 4.0, "cpu": 2.0,
                 "mem": 1.5, "saturation": 3.0}
    examples = []
    for _case in range(num_cases):
        failed = int(rng.integers(0, num_services))
        measurements = []
        for index, instance in enumerate(service_ids):
            row = {"service_instance_id": instance}
            for metric in FEATURES:
                mean, std = baseline[instance][metric]
                z = float(rng.normal(0, 0.5))
                if index == failed:
                    z += injection[metric]
                row[metric] = max(0.0001, mean + std * z)
            measurements.append(row)
        graph = build_service_graph(measurements, calls, baseline)
        examples.append((graph, [failed]))
    return examples
