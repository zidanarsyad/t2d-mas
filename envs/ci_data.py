"""Reproducible synthetic CI cycles and a generic public-results CSV loader."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class CICycle:
    """One candidate CI cycle; fault labels remain hidden from the observation."""

    observations: np.ndarray
    durations: np.ndarray
    fault_mask: np.ndarray
    cycles_since_last_failure: np.ndarray
    test_ids: tuple[str, ...]


@dataclass(frozen=True)
class CIData:
    cycles: tuple[CICycle, ...]
    dataset_version: str


def _dataset_version(payload: bytes, label: str) -> str:
    return f"{label}-{hashlib.sha256(payload).hexdigest()[:16]}"


def generate_simulated_cycles(
    num_cycles: int = 200,
    num_tests: int = 20,
    seed: int = 42,
) -> CIData:
    """Generate CI observations/outcomes with fixed-seed failure and flake patterns."""
    if num_cycles < 1 or num_tests < 2:
        raise ValueError("num_cycles must be positive and num_tests must be at least 2")
    rng = np.random.default_rng(seed)
    test_ids = tuple(f"test-{index:03d}" for index in range(num_tests))
    base_failure_prone = rng.beta(1.4, 9.0, size=num_tests)
    flaky = rng.random(num_tests) < 0.08
    last_execution = np.full(num_tests, -1, dtype=int)
    last_failure = np.full(num_tests, -10_000, dtype=int)
    failure_history = [deque(maxlen=20) for _ in range(num_tests)]
    raw: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray,
                    np.ndarray, np.ndarray]] = []

    for cycle_id in range(num_cycles):
        durations = rng.lognormal(mean=1.15, sigma=0.55, size=num_tests).astype(np.float32)
        diff_proximity = rng.beta(1.7, 2.8, size=num_tests).astype(np.float32)
        # Defect-bearing tests are biased toward tests near the changed code.
        faults = np.zeros(num_tests, dtype=np.bool_)
        if rng.random() < 0.22:
            fault_count = int(rng.integers(1, min(4, num_tests) + 1))
            probability = 0.15 + diff_proximity + base_failure_prone
            probability /= probability.sum()
            faults[rng.choice(num_tests, size=fault_count, replace=False, p=probability)] = True
        # Flaky tests sometimes fail without a real injected defect.
        outcomes = faults | (flaky & (rng.random(num_tests) < 0.18))
        cycles_since_run = np.where(last_execution < 0, cycle_id + 1,
                                    cycle_id - last_execution).astype(np.float32)
        failure_age = np.where(last_failure < 0, 1_000_000,
                               cycle_id - last_failure).astype(np.float32)
        historical_rate = np.asarray([
            float(np.mean(history)) if history else 0.0 for history in failure_history
        ], dtype=np.float32)
        raw.append((durations, faults, cycles_since_run, failure_age, historical_rate,
                    np.column_stack([flaky.astype(np.float32), diff_proximity]).astype(np.float32)))

        # The previous CI policy only ran most tests; update history for observed results.
        executed = rng.random(num_tests) < 0.88
        for test_index in np.flatnonzero(executed):
            last_execution[test_index] = cycle_id
            observed_failure = bool(outcomes[test_index])
            failure_history[test_index].append(float(observed_failure))
            if observed_failure:
                last_failure[test_index] = cycle_id

    max_duration = max(float(cycle[0].max()) for cycle in raw)
    cycles: list[CICycle] = []
    for durations, faults, cycles_since_run, failure_age, historical_rate, extras in raw:
        observations = np.column_stack([
            durations / max_duration,
            cycles_since_run,
            historical_rate,
            extras[:, 0],
            extras[:, 1],
        ]).astype(np.float32)
        cycles.append(CICycle(observations, durations, faults, failure_age, test_ids))
    version_payload = json.dumps({"seed": seed, "cycles": num_cycles,
                                  "tests": num_tests}, sort_keys=True).encode()
    return CIData(tuple(cycles), _dataset_version(version_payload, "synthetic-ci"))


def load_public_ci_csv(source: str | Path) -> CIData:
    """Load local or URL CSV test results into the same cycle format.

    Required columns: ``cycle_id,test_id,duration,failed``. Optional columns are
    ``cycles_since_execution,historical_failure_rate,flaky,diff_proximity``. When
    absent, historical features are derived from earlier rows; diff proximity and
    flaky default to zero because many public CI datasets do not expose them.
    """
    source_text = str(source)
    if source_text.startswith(("https://", "http://")):
        request = urllib.request.Request(source_text, headers={"User-Agent": "T2D-MAS-course-project/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
        label = "public-ci"
    else:
        content = Path(source_text).read_bytes()
        label = "public-ci"
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig", errors="replace"))))
    if not rows:
        raise ValueError("CI CSV is empty")
    aliases = {
        "cycle_id": ("cycle_id", "build_id", "build", "run_id"),
        "test_id": ("test_id", "test", "test_name"),
        "duration": ("duration", "duration_seconds", "runtime", "time"),
        "failed": ("failed", "failure", "result", "status"),
    }
    def pick(row: dict[str, str], name: str, default: str = "") -> str:
        normalized = {key.strip().lower(): value for key, value in row.items()}
        for key in aliases.get(name, (name,)):
            if normalized.get(key) not in (None, ""):
                return normalized[key]
        return default
    for row in rows:
        missing = [field for field in aliases if not pick(row, field)]
        if missing:
            raise ValueError(f"CI CSV row missing required fields: {', '.join(missing)}")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[pick(row, "cycle_id")].append(row)
    def cycle_order(value: str):
        try:
            return (0, float(value))
        except ValueError:
            return (1, value)
    cycle_ids = sorted(grouped, key=cycle_order)
    test_ids = tuple(sorted({pick(row, "test_id") for row in rows}))
    test_index = {name: index for index, name in enumerate(test_ids)}
    max_duration = max(float(pick(row, "duration")) for row in rows)
    duration_by_test: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        duration_by_test[pick(row, "test_id")].append(float(pick(row, "duration")))
    average_duration = {name: float(np.mean(values))
                        for name, values in duration_by_test.items()}
    previous_results: dict[str, deque[float]] = {name: deque(maxlen=20) for name in test_ids}
    last_run: dict[str, int] = {}
    last_fail: dict[str, int] = {}
    cycles = []
    for cycle_number, cycle_id in enumerate(cycle_ids):
        by_test = {pick(row, "test_id"): row for row in grouped[cycle_id]}
        observations = np.zeros((len(test_ids), 5), dtype=np.float32)
        durations = np.zeros(len(test_ids), dtype=np.float32)
        faults = np.zeros(len(test_ids), dtype=np.bool_)
        failure_age = np.full(len(test_ids), 1_000_000, dtype=np.float32)
        for test_id in test_ids:
            index = test_index[test_id]
            row = by_test.get(test_id)
            if row is None:
                # Missing rows mean the test was not reported for this build.
                durations[index] = average_duration[test_id]
                observations[index] = [0, cycle_number - last_run.get(test_id, -1),
                    float(np.mean(previous_results[test_id])) if previous_results[test_id] else 0,
                    0, 0]
                continue
            duration = float(pick(row, "duration"))
            durations[index] = duration
            failed_value = pick(row, "failed").strip().lower()
            failed = failed_value in {
                "1", "true", "yes", "failed", "failure", "fail", "error", "errored", "timedout"
            }
            cycles_since = float(row.get("cycles_since_execution") or
                                 (cycle_number - last_run.get(test_id, -1)))
            failure_rate = float(row.get("historical_failure_rate") or
                                 (np.mean(previous_results[test_id]) if previous_results[test_id] else 0.0))
            flaky = row.get("flaky", "0").strip().lower() in {"1", "true", "yes"}
            proximity = float(row.get("diff_proximity") or 0.0)
            observations[index] = [duration / max_duration if max_duration else 0,
                                   cycles_since, failure_rate, float(flaky), proximity]
            faults[index] = failed
            # Expose only past failure recency to the baseline, never this cycle's label.
            if test_id in last_fail:
                failure_age[index] = cycle_number - last_fail[test_id]
            last_run[test_id] = cycle_number
            if failed:
                last_fail[test_id] = cycle_number
            previous_results[test_id].append(float(failed))
        cycles.append(CICycle(observations, durations, faults, failure_age, test_ids))
    return CIData(tuple(cycles), _dataset_version(content, label))
