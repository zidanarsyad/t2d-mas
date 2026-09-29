"""Clean ticket text and make leakage-safe, chronological 70/10/20 splits."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d().\s-]{7,}\d)(?!\w)")
TOKEN_PATTERNS = [
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.I),
    re.compile(r"\b(?:api[_-]?key|access[_-]?token|secret|token)\s*[:=]\s*['\"]?[^\s,'\"]+", re.I),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b"),
]
VERSION_RE = re.compile(r"(?i)(\b(?:v(?:ersion)?\s*)?)\d+(?:\.\d+){1,4}(?:[-+][A-Za-z0-9.-]+)?")
BUILD_RE = re.compile(r"(?i)\b(?:build|build\s+number)\s*[:#=]?\s*\d+\b")


def clean_repeated_stack_lines(text: str) -> str:
    """Collapse consecutive duplicate stack lines without discarding context."""
    output: list[str] = []
    previous = None
    repeated = 0
    for line in str(text or "").splitlines():
        normalized = line.strip()
        if normalized and normalized == previous:
            repeated += 1
            continue
        if repeated:
            output.append(f"[repeated stack line x{repeated + 1}]")
            repeated = 0
        output.append(line.rstrip())
        previous = normalized if normalized else None
    if repeated:
        output.append(f"[repeated stack line x{repeated + 1}]")
    return "\n".join(output)


def clean_text(value: object) -> str:
    text = clean_repeated_stack_lines(str(value or ""))
    text = VERSION_RE.sub(lambda m: f"{m.group(1) or ''}<VERSION>", text)
    text = BUILD_RE.sub("build <BUILD>", text)
    text = EMAIL_RE.sub("<EMAIL>", text)
    text = PHONE_RE.sub("<PHONE>", text)
    for pattern in TOKEN_PATTERNS:
        text = pattern.sub("<TOKEN>", text)
    return text


def stable_dataset_version(frame: pd.DataFrame) -> str:
    canonical = frame.sort_values("ticket_id").to_json(orient="records", date_format="iso")
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV or Parquet normalized ticket file")
    parser.add_argument("--output-dir", default="data/output/processed")
    parser.add_argument("--dataset-version", help="Override derived version label")
    args = parser.parse_args()
    source = Path(args.input)
    frame = pd.read_parquet(source) if source.suffix.lower() == ".parquet" else pd.read_csv(source)
    required = {"ticket_id", "title", "body", "created_at", "severity"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Input missing required columns: {', '.join(missing)}")
    frame["title"] = frame["title"].map(clean_text)
    frame["body"] = frame["body"].map(clean_text)
    frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["created_at"]).sort_values(
        ["created_at", "ticket_id"], kind="stable").reset_index(drop=True)
    version = args.dataset_version or stable_dataset_version(frame)
    # Time order is preserved across boundaries to avoid future-information leakage.
    n = len(frame)
    train_end = int(n * 0.70)
    val_end = train_end + int(n * 0.10)
    splits = (("train", frame.iloc[:train_end]),
              ("val", frame.iloc[train_end:val_end]),
              ("test", frame.iloc[val_end:]))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"dataset_version": version, "split_method": "chronological", "rows": {}}
    for name, split in splits:
        output = split.copy()
        output["dataset_version"] = version
        output["pii_masked"] = True
        path = output_dir / f"{name}.parquet"
        temp_path = path.with_suffix(".parquet.tmp")
        output.to_parquet(temp_path, index=False)
        temp_path.replace(path)
        manifest["rows"][name] = len(output)
    (output_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote chronological splits {manifest['rows']}; dataset_version={version}")


if __name__ == "__main__":
    main()
