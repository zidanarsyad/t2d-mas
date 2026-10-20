"""Create the BAB 9.4 Markdown summary and requested evaluation plots."""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ARMS = ("A0", "A1", "A2", "A3")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_report(result_dir: Path) -> None:
    """Write summary table, performance charts, and held-out severity ROC points."""
    summary = _read_csv(result_dir / "summary.csv")
    tickets = _read_csv(result_dir / "per_ticket.csv")
    config = json.loads((result_dir / "config.json").read_text(encoding="utf-8"))
    seeds = config["seeds"]
    tickets_per_arm = len(seeds) * int(config["tickets_per_seed"])
    lines = [
        "# BAB 9.4 — Four-arm evaluation", "",
        f"Dataset version: `{config['dataset_version']}`; fixed seeds {', '.join(str(seed) for seed in seeds)}; "
        f"{config['tickets_per_seed']} tickets per seed, {tickets_per_arm} per arm; identical tickets are passed to all arms.",
        "Wall-clock/CPU/memory values are observations on this host. LLM tokens are character-based estimates;",
        "network bytes use the ACL/mobile bundle serializers but do not include transport framing. DORA values are simulated.",
        "Severity ROC uses the chronological 30% holdout and a TF-IDF + Platt-calibrated LinearSVC.", "",
        "| Arm | Approach | Tickets | Mean time (ms) | P95 time (ms) | Mean bytes | Messages | Token estimate | Macro-F1 | NAPFD | Rollback |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append("| {arm} | {arm_description} | {ticket_count} | {wall_time_mean_s} | {wall_time_p95_s} | {network_bytes_mean} | {messages_mean} | {llm_tokens_estimated_mean} | {macro_f1_severity} | {napfd_mean} | {rollback_rate} |".format(**{
            **row,
            # Per-ticket times are fractions of a millisecond, so seconds would round to 0.0001.
            **{key: f"{float(row[key]) * 1000:.3f}" for key in ("wall_time_mean_s", "wall_time_p95_s")},
            **{key: f"{float(row[key]):.4f}" for key in
               ("network_bytes_mean", "messages_mean", "llm_tokens_estimated_mean",
                "macro_f1_severity", "napfd_mean", "rollback_rate")},
        }))
    lines.extend(["", "## DORA-style metrics", "",
                  "| Arm | Deployments/day | Mean lead time (h) | Recovery (h) | Change failure rate | Rework rate |",
                  "|---|---:|---:|---:|---:|---:|"])
    for row in summary:
        keys = ("deployment_frequency_per_day", "lead_time_hours_mean",
                "failed_deployment_recovery_hours_mean", "change_failure_rate", "rework_rate")
        lines.append(f"| {row['arm']} | " + " | ".join(f"{float(row[key]):.4f}" for key in keys) + " |")
    stats_path = result_dir / "statistical_tests.csv"
    if stats_path.is_file():
        tests = _read_csv(stats_path)
        lines.extend(["", f"## Statistical tests (one paired block per seed, alpha = {config['alpha']})", "",
                      "| Metric | Friedman chi-square | Friedman p | Wilcoxon pairs significant after Holm |",
                      "|---|---:|---:|---:|"])
        for row in tests:
            if row["test"] != "friedman":
                continue
            pairs = [test for test in tests
                     if test["metric"] == row["metric"] and test["test"] == "wilcoxon_signed_rank"]
            significant = sum(test["significant_holm"] == "True" for test in pairs)
            lines.append(f"| {row['metric']} | {float(row['statistic']):.4f} | {float(row['p_value']):.4f} "
                         f"| {significant} of {len(pairs)} |")
        stats_note = "See `statistical_tests.csv` for paired Wilcoxon, Friedman/Nemenyi, Cliff's delta, and Holm-adjusted results."
    else:
        stats_note = "Paired statistical tests need at least two seeds, so this run is descriptive only."
    lines.extend(["", "Full per-ticket and per-stage measurements are in `per_ticket.csv` and `per_stage.csv`.",
                  stats_note,
                  "The synthetic policy-injection suite targets zero cases passed to the next stage.", ""])
    (result_dir / "BAB_9_4.md").write_text("\n".join(lines), encoding="utf-8")

    by_arm: dict[str, list[float]] = {}
    for row in tickets:
        by_arm.setdefault(row["arm"], []).append(float(row["total_wall_time_s"]))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.boxplot([by_arm[arm] for arm in ARMS], showfliers=False)
    # Name the boxes through the axis: boxplot(labels=) was removed in matplotlib 3.11 and
    # boxplot(tick_labels=) only exists from 3.9, while set_xticks(labels=) works on both.
    ax.set_xticks(range(1, len(ARMS) + 1), labels=ARMS)
    ax.set(title="Ticket wall time by evaluation arm", ylabel="Wall time (seconds)", xlabel="Arm")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(result_dir / "wall_time_by_arm.png", dpi=160,
                metadata={"Title": "Ticket wall time by evaluation arm", "Description": "dataset_version=synthetic-eval-v1"})
    plt.close(fig)

    means = {arm: statistics.mean(float(row["network_bytes"]) for row in tickets if row["arm"] == arm)
             for arm in ("A2", "A3")}
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(list(means), list(means.values()), color=("#64748b", "#0f766e"))
    ax.set(title="Mean network bytes per ticket: static vs mobile", ylabel="Bytes", xlabel="Arm")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(result_dir / "network_bytes_A2_vs_A3.png", dpi=160,
                metadata={"Title": "Network bytes A2 vs A3", "Description": "dataset_version=synthetic-eval-v1"})
    plt.close(fig)

    holdout = [row for row in tickets if row["severity_eval_split"].lower() == "true"]
    actual = np.asarray([row["severity_actual"] == "Critical" for row in holdout], dtype=int)
    scores = np.asarray([float(row["critical_probability"]) for row in holdout])
    roc = []
    for threshold in np.linspace(1.0, 0.0, 101):
        predicted = scores >= threshold
        tp = int(np.sum(predicted & (actual == 1)))
        fp = int(np.sum(predicted & (actual == 0)))
        positives, negatives = int(np.sum(actual == 1)), int(np.sum(actual == 0))
        roc.append({"threshold": float(threshold), "fpr": fp / negatives if negatives else 0.0,
                    "tpr": tp / positives if positives else 0.0,
                    "dataset_version": "synthetic-eval-v1"})
    with (result_dir / "severity_roc.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(roc[0]))
        writer.writeheader()
        writer.writerows(roc)
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.plot([row["fpr"] for row in roc], [row["tpr"] for row in roc], color="#2563eb", label="Critical vs rest")
    ax.plot([0, 1], [0, 1], "--", color="#94a3b8", label="Chance")
    ax.set(title="Severity ROC (critical class, chronological holdout)", xlabel="False positive rate", ylabel="True positive rate")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(result_dir / "severity_roc.png", dpi=160,
                metadata={"Title": "Severity ROC", "Description": "dataset_version=synthetic-eval-v1"})
    plt.close(fig)
