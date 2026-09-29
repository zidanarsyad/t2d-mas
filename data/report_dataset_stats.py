"""Create a reproducible CSV summary and chart for report table 7.3.2."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Normalized or processed CSV/Parquet tickets")
    parser.add_argument("--output-dir", default="data/output/stats")
    parser.add_argument("--dataset-version", help="Version label; otherwise read column or derive")
    args = parser.parse_args()
    source = Path(args.input)
    frame = pd.read_parquet(source) if source.suffix.lower() == ".parquet" else pd.read_csv(source)
    if frame.empty:
        raise ValueError("Cannot report statistics for an empty dataset")
    version = args.dataset_version
    if not version and "dataset_version" in frame and frame["dataset_version"].notna().any():
        version = str(frame["dataset_version"].dropna().iloc[0])
    if not version:
        digest = hashlib.sha256(frame.sort_values("ticket_id").to_json(orient="records").encode()).hexdigest()
        version = "sha256:" + digest[:16]
    duplicate_rate = float(frame["duplicate_of"].notna().mean()) if "duplicate_of" in frame else 0.0
    lengths = frame["body"].fillna("").astype(str).str.len()
    rows = [
        {"dataset_version": version, "metric": "ticket_count", "value": int(len(frame)), "category": "all"},
        {"dataset_version": version, "metric": "duplicate_ratio", "value": duplicate_rate, "category": "all"},
        {"dataset_version": version, "metric": "description_length_median_chars", "value": float(lengths.median()), "category": "all"},
        {"dataset_version": version, "metric": "description_length_p95_chars", "value": float(lengths.quantile(.95)), "category": "all"},
    ]
    distribution = frame.get("severity", pd.Series(["Unknown"] * len(frame))).fillna("Unknown").value_counts().sort_index()
    rows.extend({"dataset_version": version, "metric": "severity_count", "value": int(count), "category": str(label)}
                for label, count in distribution.items())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "dataset_stats.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    distribution.plot(kind="bar", ax=axes[0], color="#4263eb")
    axes[0].set_title("Tickets by severity")
    axes[0].set_ylabel("Tickets")
    axes[0].tick_params(axis="x", rotation=25)
    axes[1].hist(lengths, bins=20, color="#2f9e44", edgecolor="white")
    axes[1].axvline(lengths.median(), color="#e03131", linestyle="--", label="Median")
    axes[1].axvline(lengths.quantile(.95), color="#f08c00", linestyle=":", label="P95")
    axes[1].set_title("Description length")
    axes[1].set_xlabel("Characters")
    axes[1].set_ylabel("Tickets")
    axes[1].legend()
    fig.suptitle(f"Dataset statistics | {version}")
    fig.tight_layout()
    png_path = output_dir / "dataset_stats.png"
    fig.savefig(png_path, dpi=160, metadata={"Description": f"dataset_version={version}"})
    plt.close(fig)
    # A sidecar also makes the image's dataset version easy to discover in file browsers.
    (output_dir / "dataset_stats.json").write_text(json.dumps({
        "dataset_version": version,
        "artifacts": {"csv": csv_path.name, "chart": png_path.name},
    }, indent=2), encoding="utf-8")
    print(f"Wrote {csv_path} and {png_path}; dataset_version={version}")


if __name__ == "__main__":
    main()
