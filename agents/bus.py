"""FIPA-ACL-style messages on Redis Streams, with an in-memory stand-in for local runs.

The stream is the shared conversation log: every handoff is appended to it, the
dashboard replays it, and the audit log records each message before and after it
is published.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

PERFORMATIVES = {"cfp", "propose", "refuse", "accept-proposal", "reject-proposal", "inform", "failure"}
STREAM_MAXLEN = 10_000  # keep the conversation log bounded
logger = logging.getLogger(__name__)


def serialize_acl_message(message: "ACLMessage") -> bytes:
    """Return the compact JSON wire payload used by Redis Streams."""
    return json.dumps(asdict(message), separators=(",", ":")).encode("utf-8")


@dataclass
class ACLMessage:
    # The field layout is part of the evaluation's byte counts, so do not add,
    # remove or reorder fields. `signature` is reserved for signed messages and is
    # left empty in this prototype (only mobile bundles are signed).
    performative: str
    correlation_id: str
    content: dict[str, Any]
    policy_context: dict[str, Any] = field(default_factory=dict)
    signature: str = ""
    sender: str = ""
    receiver: list[str] = field(default_factory=list)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ontology: str = "t2d-mas/v1"

    def __post_init__(self) -> None:
        if self.performative not in PERFORMATIVES:
            raise ValueError(f"unsupported FIPA performative: {self.performative}")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")


def _row(entry_id: str, payload: str) -> dict[str, Any]:
    """Shape one stored message the way the dashboard reads it."""
    millis = int(entry_id.split("-")[0])
    return {**json.loads(payload), "stream_id": entry_id,
            "occurred_at": datetime.fromtimestamp(millis / 1000, timezone.utc).isoformat()}


class RedisStreamBus:
    """Thin redis-py wrapper around one append-only stream."""

    kind = "redis"

    def __init__(self, redis_url: str, stream: str = "t2d:messages") -> None:
        self.redis_url = redis_url
        self.stream = stream
        self._client: Any = None

    async def connect(self, timeout_s: float = 1.0) -> None:
        from redis.asyncio import Redis
        self._client = Redis.from_url(self.redis_url, decode_responses=True,
                                      socket_connect_timeout=timeout_s)
        await self._client.ping()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def publish(self, message: ACLMessage) -> str:
        if self._client is None:
            raise RuntimeError("connect() must be called before publish()")
        payload = serialize_acl_message(message)
        entry_id = await self._client.xadd(self.stream, {"message": payload.decode("utf-8")},
                                           maxlen=STREAM_MAXLEN, approximate=True)
        logger.info("ACL message published", extra={"correlation_id": message.correlation_id})
        return entry_id

    async def recent(self, count: int = 200) -> list[dict[str, Any]]:
        """Read recent traffic, oldest first, without consuming it."""
        if self._client is None:
            raise RuntimeError("connect() must be called before reading messages")
        rows = await self._client.xrevrange(self.stream, count=count)
        return [_row(entry_id, fields["message"]) for entry_id, fields in reversed(rows)]


class InMemoryBus:
    """Local-mode stand-in for Redis Streams with the same publish/recent interface."""

    kind = "memory"

    def __init__(self, maxlen: int = STREAM_MAXLEN) -> None:
        self._rows: deque[tuple[str, str]] = deque(maxlen=maxlen)
        self._sequence = 0

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def publish(self, message: ACLMessage) -> str:
        self._sequence += 1
        entry_id = f"{int(time.time() * 1000)}-{self._sequence}"
        self._rows.append((entry_id, serialize_acl_message(message).decode("utf-8")))
        return entry_id

    async def recent(self, count: int = 200) -> list[dict[str, Any]]:
        return [_row(entry_id, payload) for entry_id, payload in list(self._rows)[-count:]]
