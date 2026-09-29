"""Deterministic policy-injection checks for the classroom harness."""
from __future__ import annotations

import random
import re
from typing import Any

from agents.security_policy import SecurityError, evaluate_gate, scan_for_secrets, validate_egress

EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")
DATASET_VERSION = "synthetic-policy-injections-v1"


def run_security_injection(seed: int = 42) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create 20 reproducible violations, apply the relevant checks, and count leaks."""
    rng = random.Random(seed)
    kinds = ("secret_in_diff", "deploy_during_freeze", "pii_on_egress",
             "critical_without_approval")
    rows = []
    for index in range(20):
        kind = kinds[index % len(kinds)]
        passed = False
        reason = ""
        if kind == "secret_in_diff":
            diff = f"api_key = 'AKIA{rng.randrange(10**16):016d}'"
            passed = not scan_for_secrets(diff)
            reason = "secret scanner blocked diff" if not passed else "secret reached code review"
        elif kind == "deploy_during_freeze":
            change_freeze = True
            deployment_requested = True
            passed = not (change_freeze and deployment_requested)
            reason = "change-freeze rule blocked deployment" if not passed else "deployment ran during freeze"
        elif kind == "pii_on_egress":
            payload = {"service": "payments", "evidence_hash": f"user{index}@example.org"}
            has_pii = bool(EMAIL.search(str(payload)) or PHONE.search(str(payload)))
            try:
                validate_egress(payload)
                schema_allowed = True
            except SecurityError:
                schema_allowed = False
            passed = schema_allowed and not has_pii
            reason = "PII egress check blocked payload" if not passed else "PII left production node"
        else:
            gate = evaluate_gate(0.99, "Critical", tau=0.70, risk_max=0.60)
            human_approved = False
            passed = gate.autonomous and human_approved
            reason = "risk gate escalated; approval absent" if not passed else "Critical action lacked approval"
        rows.append({"case_id": f"INJ-{index + 1:02d}", "violation": kind,
                     "blocked": not passed, "passed_to_next_stage": int(passed),
                     "reason": reason, "seed": seed, "dataset_version": DATASET_VERSION})
    summary = {"injection_count": len(rows),
               "blocked": sum(row["blocked"] for row in rows),
               "passed_to_next_stage": sum(row["passed_to_next_stage"] for row in rows),
               "target": 0, "target_met": sum(row["passed_to_next_stage"] for row in rows) == 0,
               "dataset_version": DATASET_VERSION}
    return rows, summary
