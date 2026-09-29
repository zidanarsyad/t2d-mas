"""Append-only audit sinks used by agents and the orchestrator."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class AuditEvent:
    actor_id: str
    action: str
    decision: str
    correlation_id: str
    ticket_id: str | None = None
    confidence: float | None = None
    human_approved: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditSink(Protocol):
    def append(self, event: AuditEvent) -> None: ...


class MemoryAuditSink:
    """Simple test/demo sink; events can only be appended."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)


class PostgresAuditSink:
    """Insert audit events into the append-only table defined in data/schema.sql."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL is required for PostgresAuditSink")

    def append(self, event: AuditEvent) -> None:
        # psycopg is imported lazily so unit tests do not need a running database.
        import psycopg

        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """INSERT INTO audit_log
                   (occurred_at, correlation_id, actor_id, action, ticket_id,
                    decision, human_approved, details)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                (event.occurred_at, event.correlation_id, event.actor_id,
                 event.action, event.ticket_id, event.decision,
                 event.human_approved, json.dumps(asdict(event))),
            )
