"""Load GitBugs/GitHub issue exports into the shared ticket table."""
from __future__ import annotations

import argparse
import json

try:  # Supports both `python data/loaders/gitbugs.py` and `python -m ...`.
    from .common import canonical_row, common_args, pick, read_source, version_for, write_outputs
except ImportError:
    from common import canonical_row, common_args, pick, read_source, version_for, write_outputs


def normalize(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        repo = str(pick(record, "repository", "repo", "project", default="gitbugs")).strip()
        issue_id = pick(record, "ticket_id", "issue_id", "id", "number", "bug_id")
        # Prefix IDs with repository to avoid collisions across GitHub projects.
        ticket_id = str(issue_id)
        if "/" not in ticket_id and ":" not in ticket_id:
            ticket_id = f"{repo}:{ticket_id}"
        labels = pick(record, "severity", "priority", "labels", "label", default="")
        if isinstance(labels, (list, dict)):
            labels = json.dumps(labels)
        rows.append(canonical_row(
            ticket_id=ticket_id,
            title=pick(record, "title", "summary"),
            body=pick(record, "body", "description", "text", "issue_body"),
            component=pick(record, "component", "area", "repository", "repo", "project"),
            severity=labels,
            created_at=pick(record, "created_at", "creation_time", "created", "date"),
            duplicate_of=pick(record, "duplicate_of", "dupe_of", "duplicate", default=None),
            source="gitbugs",
        ))
    # Stable IDs make output deterministic, even if source ordering changes.
    return sorted({row["ticket_id"]: row for row in rows}.values(), key=lambda row: row["ticket_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    common_args(parser, "data/output/gitbugs.parquet")
    args = parser.parse_args()
    rows = normalize(read_source(args.input, args.url))
    version = version_for(rows, args.dataset_version)
    write_outputs(rows, version, args.parquet, args.database_url)
    print(f"Loaded {len(rows)} GitBugs tickets; dataset_version={version}")


if __name__ == "__main__":
    main()
