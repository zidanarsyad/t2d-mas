"""FIPA-ACL-style message bus on Redis Streams with worker consumer groups."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

PERFORMATIVES = {"cfp", "propose", "refuse", "accept-proposal", "reject-proposal", "inform", "failure"}
logger = logging.getLogger(__name__)


def serialize_acl_message(message: "ACLMessage") -> bytes:
    """Return the compact JSON wire payload used by Redis Streams."""
    return json.dumps(asdict(message), separators=(",", ":")).encode("utf-8")


@dataclass
class ACLMessage:
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


class RedisStreamBus:
    """Thin redis-py wrapper. Separate consumer names allow parallel workers."""

    def __init__(self, redis_url: str, stream: str = "t2d:messages") -> None:
        self.redis_url = redis_url
        self.stream = stream
        self._client: Any = None
        self.messages_published = 0
        self.bytes_published = 0

    async def connect(self) -> None:
        from redis.asyncio import Redis
        self._client = Redis.from_url(self.redis_url, decode_responses=True)
        await self._client.ping()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def publish(self, message: ACLMessage) -> str:
        if self._client is None:
            raise RuntimeError("connect() must be called before publish()")
        payload = serialize_acl_message(message)
        entry_id = await self._client.xadd(self.stream, {"message": payload.decode("utf-8")})
        self.messages_published += 1
        self.bytes_published += len(payload)
        logger.info("ACL message published", extra={"correlation_id": message.correlation_id})
        return entry_id

    async def ensure_group(self, group: str, start_id: str = "0") -> None:
        if self._client is None:
            raise RuntimeError("connect() must be called before ensure_group()")
        try:
            await self._client.xgroup_create(self.stream, group, id=start_id, mkstream=True)
        except Exception as exc:
            # Redis reports BUSYGROUP if multiple workers initialize together.
            if "BUSYGROUP" not in str(exc):
                raise

    async def read_group(self, group: str, consumer: str, count: int = 10,
                         block_ms: int = 1000) -> list[tuple[str, ACLMessage]]:
        """Read messages pending for this consumer group; distinct consumer IDs parallelize work."""
        if self._client is None:
            raise RuntimeError("connect() must be called before read_group()")
        rows = await self._client.xreadgroup(group, consumer, {self.stream: ">"}, count=count, block=block_ms)
        messages: list[tuple[str, ACLMessage]] = []
        for _, entries in rows:
            for entry_id, fields in entries:
                messages.append((entry_id, ACLMessage(**json.loads(fields["message"]))))
        for _, message in messages:
            logger.info("ACL message received", extra={"correlation_id": message.correlation_id})
        return messages

    async def ack(self, group: str, entry_id: str) -> int:
        if self._client is None:
            raise RuntimeError("connect() must be called before ack()")
        return await self._client.xack(self.stream, group, entry_id)
