"""Minimal in-process event fan-out for the FastAPI server-sent event stream."""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator


class EventHub:
    """Broadcast small JSON-ready updates to each connected browser client."""

    def __init__(self, queue_size: int = 100) -> None:
        self.queue_size = queue_size
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    async def publish(self, event: dict[str, Any]) -> None:
        for queue in tuple(self._subscribers):
            # A slow dashboard should not block an agent or keep stale updates forever.
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    async def subscribe(self, heartbeat_seconds: float | None = None) -> AsyncIterator[dict[str, Any] | None]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(self.queue_size)
        self._subscribers.add(queue)
        try:
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                except TimeoutError:
                    # Cancel only the queue wait; keep this subscription alive.
                    yield None
        finally:
            self._subscribers.discard(queue)


event_hub = EventHub()
