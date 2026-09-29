"""Load Eclipse or Mozilla Bugzilla issues from a local export or public REST API."""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

try:
    from .common import canonical_row, common_args, pick, read_source, version_for, write_outputs
except ImportError:
    from common import canonical_row, common_args, pick, read_source, version_for, write_outputs


HOSTS = {
    "mozilla": "https://bugzilla.mozilla.org/rest/bug",
    "eclipse": "https://bugs.eclipse.org/bugs/rest/bug",
}


def fetch_bugzilla(host: str, limit: int, max_records: int) -> list[dict]:
    """Page through the public Bugzilla API; cap rows for a manageable class demo."""
    records: list[dict] = []
    offset = 0
    fields = "id,summary,description,product,component,severity,priority,creation_time,dupe_of"
    while offset < max_records:
        params = urllib.parse.urlencode({
            "limit": min(limit, max_records - offset),
            "offset": offset,
            "include_fields": fields,
            "order": "bug_id",
        })
        request = urllib.request.Request(
            f"{HOSTS[host]}?{params}", headers={"User-Agent": "T2D-MAS-course-project/1.0"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
        page = payload.get("bugs", [])
        if not page:
            break
        records.extend(page)
        offset += len(page)
    return records


def normalize(records: list[dict], host: str) -> list[dict]:
    rows = []
    for record in records:
        rows.append(canonical_row(
            ticket_id=f"{host}:{pick(record, 'id', 'bug_id', 'ticket_id')}",
            title=pick(record, "summary", "title"),
            body=pick(record, "description", "body"),
            component=pick(record, "component", "product"),
            severity=pick(record, "severity", "priority"),
            created_at=pick(record, "creation_time", "created_at"),
            duplicate_of=(f"{host}:{pick(record, 'dupe_of')}"
                          if pick(record, "dupe_of") else None),
            source=host,
        ))
    return sorted({row["ticket_id"]: row for row in rows}.values(), key=lambda row: row["ticket_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    common_args(parser, "data/output/eclipse_mozilla.parquet")
    parser.add_argument("--host", choices=sorted(HOSTS), default="mozilla")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--max-records", type=int, default=5000)
    args = parser.parse_args()
    records = (read_source(args.input, None) if args.input
               else read_source(None, args.url) if args.url
               else fetch_bugzilla(args.host, args.limit, args.max_records))
    rows = normalize(records, args.host)
    version = version_for(rows, args.dataset_version)
    write_outputs(rows, version, args.parquet, args.database_url)
    print(f"Loaded {len(rows)} {args.host.title()} tickets; dataset_version={version}")


if __name__ == "__main__":
    main()
