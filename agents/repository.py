"""Blackboard storage: PostgreSQL in Docker, an in-memory twin for local runs and tests.

Both versions enforce the same rule as the database triggers in data/schema.sql:
a change can be marked merged, and a production deployment can be recorded, only
with human_approved = TRUE. The in-memory version raises GuardViolation where
PostgreSQL would raise an exception.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from agents.audit import MemoryAuditSink
from agents.policy import Policy

SANDBOX_DATASET = "sandbox-v2"  # tickets created through the dashboard


class GuardViolation(RuntimeError):
    """Raised when a write would merge or deploy without a recorded human approval."""


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _event_view(occurred_at: Any, actor_id: str, action: str, decision: str,
                envelope: dict[str, Any] | None) -> dict[str, Any]:
    """Flatten one audit row into what the dashboard's saved-history view shows."""
    envelope = envelope if isinstance(envelope, dict) else {}
    details = envelope.get("details", envelope)
    details = details if isinstance(details, dict) else {}
    output = details.get("output") or details.get("result") or details.get("content")
    inputs = details.get("inputs") or {}
    return {
        "occurred_at": _iso(occurred_at), "agent": actor_id, "action": action, "decision": decision,
        "stage": details.get("stage"), "execution_mode": details.get("execution_mode"),
        "output": output, "message_id": details.get("message_id"),
        "receivers": details.get("receivers"), "performative": details.get("performative"),
        "checkpoint": details.get("checkpoint") or details.get("gate"),
        "approver": details.get("approver"), "note": details.get("reason"),
        "intent": details.get("intent"), "interpretation": details.get("interpretation"),
        "revision": details.get("revision"), "next_stage": details.get("next_stage"),
        # Gate evidence, so a saved run can show what the policy compared.
        "confidence": envelope.get("confidence", inputs.get("confidence")),
        "tau": inputs.get("tau"), "risk": inputs.get("risk"), "risk_max": inputs.get("risk_max"),
    }


class MemoryRepository:
    """Process-local blackboard; everything is lost when the server stops."""

    kind = "memory"

    def __init__(self, audit: MemoryAuditSink) -> None:
        self.audit = audit
        self.tickets: dict[str, dict[str, Any]] = {}
        self.code_changes: dict[str, dict[str, Any]] = {}
        self.deployments: dict[str, dict[str, Any]] = {}
        self.policy_row: dict[str, Any] | None = None
        self.baselines: dict[str, dict[str, dict[str, Any]]] = {}

    # Tickets ---------------------------------------------------------------
    def save_ticket(self, ticket: dict[str, Any]) -> None:
        stored = {"created_on": datetime.now(timezone.utc).isoformat(), **ticket}
        self.tickets.setdefault(ticket["ticket_id"], stored)

    def update_ticket(self, ticket_id: str, **fields: Any) -> None:
        if ticket_id in self.tickets:
            self.tickets[ticket_id].update(fields)

    def recent_ticket_texts(self, limit: int = 500) -> list[dict[str, Any]]:
        rows = list(self.tickets.values())[-limit:]
        return [{"ticket_id": row["ticket_id"], "title": row.get("title", ""), "body": row.get("body", ""),
                 "duplicate_of": row.get("duplicate_of"), "created_at": row.get("created_at")}
                for row in reversed(rows)]

    # Irreversible actions --------------------------------------------------
    def save_code_change(self, change: dict[str, Any]) -> None:
        if change.get("merged") and not change.get("human_approved"):
            raise GuardViolation("merge requires human_approved = TRUE")
        self.code_changes[change["change_id"]] = {"merged": False, "human_approved": False, **change}

    def mark_merged(self, change_id: str, approver: str, human_approved: bool) -> None:
        if not human_approved:
            raise GuardViolation("merge requires human_approved = TRUE")
        self.code_changes[change_id].update(merged=True, human_approved=True, approved_by=approver,
                                            merged_at=datetime.now(timezone.utc).isoformat())

    def save_deployment(self, deployment: dict[str, Any]) -> None:
        if deployment.get("status") == "deployed" and not deployment.get("human_approved"):
            raise GuardViolation("deployment requires human_approved = TRUE")
        self.deployments[deployment["deployment_id"]] = dict(deployment)

    # Policy and SLO baselines ----------------------------------------------
    def ensure_seed(self, policy: Policy, baselines: dict[str, dict[str, dict[str, Any]]]) -> None:
        # Memory mode always uses the code-default policy, so only the baselines are stored.
        for service, metrics in baselines.items():
            self.baselines.setdefault(service, {}).update(
                {metric: dict(values) for metric, values in metrics.items()})

    def load_policy(self) -> dict[str, Any] | None:
        return self.policy_row

    def slo_baselines(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {service: dict(metrics) for service, metrics in self.baselines.items()}

    # Saved history (dashboard "Saved runs") ---------------------------------
    def ticket_history(self, limit: int) -> dict[str, Any]:
        events: dict[str, list[dict[str, Any]]] = {}
        for event in self.audit.events:
            if event.ticket_id in self.tickets:
                events.setdefault(event.ticket_id, []).append(_event_view(
                    event.occurred_at, event.actor_id, event.action, event.decision, asdict(event)))
        rows = [row for row in reversed(self.tickets.values()) if row["ticket_id"] in events][:limit]
        items = [{"ticket_id": row["ticket_id"], "title": row.get("title"), "body": row.get("body"),
                  "severity": row.get("severity"), "process_started_at": events[row["ticket_id"]][0]["occurred_at"],
                  "events": events[row["ticket_id"]]} for row in rows]
        return {"total": len(items), "limit": limit, "items": items}


class PostgresRepository:
    """The same interface backed by data/schema.sql; one short connection per call."""

    kind = "postgres"

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self):
        import psycopg  # imported lazily so local mode does not need a database driver
        return psycopg.connect(self.database_url)

    def check_connection(self) -> None:
        with self._connect() as connection:
            connection.execute("SELECT 1")

    def save_ticket(self, ticket: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO tickets (ticket_id, source, title, body, component, severity, created_at,
                       duplicate_of, dataset_version, pii_masked, status, language, app_version, platform,
                       parent_ticket_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s)
                   ON CONFLICT (ticket_id) DO NOTHING""",
                (ticket["ticket_id"], ticket.get("source", "sandbox"), ticket["title"], ticket["body"],
                 ticket.get("component"), ticket.get("severity", "Unknown"), ticket.get("created_at"),
                 ticket.get("duplicate_of"), ticket.get("dataset_version", SANDBOX_DATASET),
                 ticket.get("status"), ticket.get("language"), ticket.get("app_version"),
                 ticket.get("platform"), ticket.get("parent_ticket_id")))

    def update_ticket(self, ticket_id: str, **fields: Any) -> None:
        allowed = {"severity", "status", "component", "duplicate_of", "language"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        assignments = ", ".join(f"{key} = %s" for key in updates)
        with self._connect() as connection:
            connection.execute(f"UPDATE tickets SET {assignments}, updated_on = now() WHERE ticket_id = %s",
                               (*updates.values(), ticket_id))

    def recent_ticket_texts(self, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT ticket_id, title, body, duplicate_of, created_at FROM tickets
                   WHERE dataset_version = %s ORDER BY created_on DESC LIMIT %s""",
                (SANDBOX_DATASET, limit)).fetchall()
        return [{"ticket_id": row[0], "title": row[1], "body": row[2], "duplicate_of": row[3],
                 "created_at": _iso(row[4])} for row in rows]

    def save_code_change(self, change: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO code_changes (change_id, ticket_id, repository, branch_name, title, diff_summary,
                       files, tests_added, additions, deletions)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                   ON CONFLICT (change_id) DO NOTHING""",
                (change["change_id"], change["ticket_id"], change["repository"], change.get("branch_name"),
                 change.get("title"), change.get("diff_summary"), json.dumps(change.get("files", [])),
                 json.dumps(change.get("tests_added", [])), change.get("additions", 0),
                 change.get("deletions", 0)))

    def mark_merged(self, change_id: str, approver: str, human_approved: bool) -> None:
        # The trigger rejects merged = TRUE without human_approved = TRUE.
        with self._connect() as connection:
            connection.execute(
                """UPDATE code_changes SET merged = TRUE, human_approved = %s, approved_by = %s,
                       merged_at = now() WHERE change_id = %s""", (human_approved, approver, change_id))

    def save_deployment(self, deployment: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO deployments (deployment_id, change_id, ticket_id, environment, strategy,
                       risk_score, status, human_approved, approved_by, slo_breach, deployed_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           CASE WHEN %s = 'deployed' THEN now() ELSE NULL END)""",
                (deployment["deployment_id"], deployment["change_id"], deployment["ticket_id"],
                 deployment["environment"], deployment["strategy"], deployment.get("risk_score"),
                 deployment["status"], deployment.get("human_approved", False), deployment.get("approved_by"),
                 deployment.get("slo_breach", False), deployment["status"]))

    def ensure_seed(self, policy: Policy, baselines: dict[str, dict[str, dict[str, Any]]]) -> None:
        """Insert the code defaults once; edits made in the database are kept."""
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO policies (policy_id, name, tau, risk_max, rules, approved_by)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s) ON CONFLICT (policy_id) DO NOTHING""",
                (policy.policy_id, "Report defaults", policy.tau, policy.risk_max,
                 json.dumps(policy.rules()), "seeded from agents/policy.py"))
            for service, metrics in baselines.items():
                for metric, values in metrics.items():
                    connection.execute(
                        """INSERT INTO slo_baselines (service, metric, window_minutes, baseline_mean,
                               baseline_std, slo_threshold, unit, dataset_version)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (service, metric) DO NOTHING""",
                        (service, metric, values["window_minutes"], values["mean"], values["std"],
                         values["slo"], values["unit"], "simulated-baseline-v1"))

    def load_policy(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT policy_id, tau, risk_max, rules FROM policies WHERE active
                   ORDER BY version DESC, created_at DESC LIMIT 1""").fetchone()
        return {"policy_id": row[0], "tau": row[1], "risk_max": row[2], "rules": row[3]} if row else None

    def slo_baselines(self) -> dict[str, dict[str, dict[str, Any]]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT service, metric, window_minutes, baseline_mean, baseline_std, slo_threshold, unit
                   FROM slo_baselines""").fetchall()
        baselines: dict[str, dict[str, dict[str, Any]]] = {}
        for service, metric, window, mean, std, slo, unit in rows:
            baselines.setdefault(service, {})[metric] = {
                "window_minutes": window, "mean": mean, "std": std, "slo": slo, "unit": unit}
        return baselines

    def ticket_history(self, limit: int) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT ticket_id, title, body, severity,
                          (SELECT MIN(occurred_at) FROM audit_log WHERE audit_log.ticket_id = tickets.ticket_id)
                   FROM tickets
                   WHERE EXISTS (SELECT 1 FROM audit_log WHERE audit_log.ticket_id = tickets.ticket_id)
                   ORDER BY created_on DESC, ticket_id DESC LIMIT %s""", (limit,)).fetchall()
            ids = [row[0] for row in rows]
            audit_rows = connection.execute(
                """SELECT occurred_at, actor_id, action, decision, details, ticket_id
                   FROM audit_log WHERE ticket_id = ANY(%s) ORDER BY occurred_at, audit_id""",
                (ids,)).fetchall() if ids else []
        events: dict[str, list[dict[str, Any]]] = {ticket_id: [] for ticket_id in ids}
        for occurred_at, actor_id, action, decision, details, ticket_id in audit_rows:
            if ticket_id in events:
                events[ticket_id].append(_event_view(occurred_at, actor_id, action, decision, details))
        items = [{"ticket_id": row[0], "title": row[1], "body": row[2], "severity": row[3],
                  "process_started_at": _iso(row[4]), "events": events.get(row[0], [])} for row in rows]
        return {"total": len(items), "limit": limit, "items": items}
