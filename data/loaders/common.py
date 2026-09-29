"""Shared loader helpers; the public schema stays deliberately small."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def read_source(path: str | None, url: str | None) -> list[dict[str, Any]]:
    """Read a local CSV/JSON/JSONL/Parquet file or download the same formats."""
    if path:
        raw = Path(path).read_bytes()
        suffix = Path(path).suffix.lower()
    elif url:
        request = urllib.request.Request(url, headers={"User-Agent": "T2D-MAS-course-project/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
        suffix = Path(url.split("?", 1)[0]).suffix.lower()
    else:
        raise ValueError("Provide either --input PATH or --url URL")
    return parse_records(raw, suffix)


def parse_records(raw: bytes, suffix: str) -> list[dict[str, Any]]:
    if suffix == ".parquet":
        import pandas as pd
        return pd.read_parquet(__import__("io").BytesIO(raw)).to_dict(orient="records")
    text = raw.decode("utf-8-sig", errors="replace")
    if suffix in (".jsonl", ".ndjson"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if suffix == ".json" or text.lstrip().startswith(("{", "[")):
        value = json.loads(text)
        if isinstance(value, dict):
            value = value.get("bugs", value.get("issues", value.get("data", [value])))
        return list(value)
    return list(csv.DictReader(text.splitlines()))


def pick(row: dict[str, Any], *names: str, default: Any = "") -> Any:
    normalized = {str(k).strip().lower().replace(" ", "_"): v for k, v in row.items()}
    for name in names:
        key = name.lower().replace(" ", "_")
        if normalized.get(key) not in (None, ""):
            return normalized[key]
    return default


def normalize_severity(value: Any) -> str:
    raw = str(value or "").strip().lower()
    tokens = set(re.findall(r"[a-z0-9]+", raw))
    if tokens & {"critical", "blocker", "showstopper", "p1", "s1", "highest"}:
        return "Critical"
    if tokens & {"high", "major", "p2", "s2", "important"}:
        return "High"
    if tokens & {"medium", "normal", "p3", "s3", "moderate"}:
        return "Medium"
    if tokens & {"low", "minor", "trivial", "p4", "p5", "s4", "s5"}:
        return "Low"
    return "Unknown"


def normalize_datetime(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def canonical_row(ticket_id: Any, title: Any, body: Any, component: Any,
                  severity: Any, created_at: Any, duplicate_of: Any,
                  source: str) -> dict[str, Any]:
    identifier = str(ticket_id or "").strip()
    if not identifier:
        raise ValueError("Source row has no ticket identifier")
    duplicate = str(duplicate_of).strip() if duplicate_of not in (None, "") else None
    return {
        "ticket_id": identifier,
        "title": str(title or "").strip() or "(untitled)",
        "body": str(body or "").strip(),
        "component": str(component or "").strip() or None,
        "severity": normalize_severity(severity),
        "created_at": normalize_datetime(created_at),
        "duplicate_of": duplicate,
        "source": source,
    }


def version_for(rows: Iterable[dict[str, Any]], requested: str | None) -> str:
    if requested:
        return requested
    serialized = json.dumps(list(rows), sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def write_outputs(rows: list[dict[str, Any]], version: str, parquet: str,
                  database_url: str | None) -> None:
    import pandas as pd
    target = Path(parquet)
    target.parent.mkdir(parents=True, exist_ok=True)
    enriched = [{**row, "dataset_version": version, "pii_masked": False} for row in rows]
    # Parquet is replaced atomically so rerunning a loader never appends duplicates.
    temporary = target.with_name(target.name + ".tmp")
    pd.DataFrame(enriched).to_parquet(temporary, index=False)
    os.replace(temporary, target)
    if database_url:
        import psycopg
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """INSERT INTO tickets
                    (ticket_id, source, title, body, component, severity, created_at,
                     duplicate_of, dataset_version, pii_masked)
                    VALUES (%(ticket_id)s, %(source)s, %(title)s, %(body)s, %(component)s,
                            %(severity)s, %(created_at)s, %(duplicate_of)s, %(dataset_version)s,
                            %(pii_masked)s)
                    ON CONFLICT (ticket_id) DO UPDATE SET
                      source=EXCLUDED.source, title=EXCLUDED.title, body=EXCLUDED.body,
                      component=EXCLUDED.component, severity=EXCLUDED.severity,
                      created_at=EXCLUDED.created_at, duplicate_of=EXCLUDED.duplicate_of,
                      dataset_version=EXCLUDED.dataset_version, pii_masked=EXCLUDED.pii_masked,
                      updated_on=now()""",
                    enriched,
                )


def common_args(parser: Any, default_parquet: str = "data/output/tickets.parquet") -> None:
    parser.add_argument("--input", help="Local CSV, JSON, JSONL, or Parquet dataset")
    parser.add_argument("--url", help="Dataset URL; downloaded only when this option is used")
    parser.add_argument("--parquet", default=default_parquet)
    parser.add_argument("--dataset-version", help="Optional human-readable version label")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"),
                        help="PostgreSQL URL; omit to write only Parquet")
