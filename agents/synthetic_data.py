"""Deterministic synthetic ticket text shared by the evaluation and history UI."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any


SEVERITIES = ("Low", "Medium", "High", "Critical")


def make_synthetic_tickets(seed: int, count: int) -> list[dict[str, Any]]:
    """Recreate the exact seeded course-project tickets used by the eval harness."""
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        severity = SEVERITIES[index % len(SEVERITIES)]
        parent_index = index - 4 if index >= 4 and index % 7 == 0 else None
        duplicate_of = f"TCK-{parent_index:05d}" if parent_index is not None else ""
        keyword = {"Low": "minor cosmetic", "Medium": "feature regression",
                   "High": "service outage", "Critical": "critical data loss"}[severity]
        if parent_index is not None:
            parent = rows[parent_index]
            title = f"Follow-up: {parent['title']}"
            body = f"{parent['body']} Additional reproduction details from report {index}."
            component = parent["component"]
        else:
            title = f"{keyword} in component-{index % 8}"
            body = (f"{title}. Reproduction details for build {1 + index % 13}. "
                    f"Impact score {rng.randrange(1, 100)}.")
            component = f"component-{index % 8}"
        created_at = (datetime(2026, 1, 1, tzinfo=timezone.utc)
                      + timedelta(hours=index)).isoformat()
        rows.append({"ticket_id": f"TCK-{index:05d}", "title": title, "body": body,
                     "component": component, "severity": severity,
                     "created_at": created_at, "duplicate_of": duplicate_of,
                     "is_fault": int(severity in ("High", "Critical"))})
    return rows


def synthetic_review_note(severity: str, approved: bool) -> str:
    """Return an illustrative note, clearly tied to a synthetic review outcome."""
    if approved:
        if severity == "Critical":
            return "Synthetic reviewer accepted after confirming incident impact, mitigation scope, and a rollback owner."
        return "Synthetic reviewer accepted after confirming affected services, customer impact, and the recovery plan."
    if severity == "Critical":
        return "Synthetic reviewer rejected because impact evidence or the safe mitigation and rollback plan was incomplete."
    return "Synthetic reviewer rejected because the outage scope and recovery evidence need clarification."
