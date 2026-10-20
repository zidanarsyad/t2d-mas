"""Check that a new evaluation run reproduces a reference run exactly.

Usage:
    python -m eval.compare_runs results/20260930T020846305626 <new-run-folder>

Every cell must match as text, except host measurements (wall time, CPU,
memory) and the simulated lead time that is derived from wall time. Those
change from machine to machine even with fixed seeds, so they are skipped.
The exit code is 1 when anything else differs.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# Columns measured on the host (or derived from host timing); they cannot repeat exactly.
TIMING_COLUMNS = {
    "wall_time_s", "total_wall_time_s", "wall_time_mean_s", "wall_time_median_s", "wall_time_p95_s",
    "cpu_seconds", "cpu_seconds_mean", "peak_memory_bytes", "peak_memory_bytes_max",
    "lead_time_hours_simulated", "lead_time_hours_mean",
}
# Statistical-test rows computed on those host measurements.
TIMING_METRICS = {"total_wall_time_s", "cpu_seconds"}
CSV_FILES = ("summary.csv", "per_ticket.csv", "per_stage.csv", "statistical_tests.csv",
             "security_injection_cases.csv", "security_injection_summary.csv")


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [row for row in rows if row.get("metric") not in TIMING_METRICS]


def compare_csv(reference: Path, candidate: Path, limit: int = 5) -> list[str]:
    """Return human-readable differences between two CSV files (empty when equal)."""
    if not candidate.exists():
        return [f"{candidate.name}: missing in the new run"]
    old_rows, new_rows = _rows(reference), _rows(candidate)
    if len(old_rows) != len(new_rows):
        return [f"{reference.name}: {len(old_rows)} rows vs {len(new_rows)} rows"]
    problems = []
    for index, (old, new) in enumerate(zip(old_rows, new_rows), start=2):
        for column in old:
            if column in TIMING_COLUMNS:
                continue
            if old[column] != new.get(column):
                problems.append(f"{reference.name} line {index}, {column}: {old[column]!r} vs {new.get(column)!r}")
                if len(problems) >= limit:
                    return problems + ["(more differences not shown)"]
    return problems


def compare_runs(reference_dir: Path, candidate_dir: Path) -> list[str]:
    problems = []
    for name in CSV_FILES:
        if (reference_dir / name).exists():
            problems += compare_csv(reference_dir / name, candidate_dir / name)
    old_config = json.loads((reference_dir / "config.json").read_text(encoding="utf-8"))
    new_config = json.loads((candidate_dir / "config.json").read_text(encoding="utf-8"))
    if old_config != new_config:
        problems.append("config.json differs")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    problems = compare_runs(Path(argv[0]), Path(argv[1]))
    for line in problems:
        print(line)
    print("Runs match on every non-timing value." if not problems else f"{len(problems)} difference(s) found.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
