"""Agent messages are masked and audited before they reach the bus; both buses read back in order."""
import asyncio

from agents.audit import MemoryAuditSink
from agents.bus import ACLMessage, InMemoryBus, RedisStreamBus
from agents.events import EventHub
from agents.messaging import MessageService


def test_published_message_is_audited_before_the_bus_and_masks_text():
    audit = MemoryAuditSink()

    class Bus:
        async def publish(self, message):
            assert audit.events[-1].decision == "publish_authorized"
            assert audit.events[-1].details["content"]["note"] == "Contact <EMAIL>"
            return "1-0"

    service = MessageService(Bus(), audit, EventHub())
    stream_id = asyncio.run(service.publish(ACLMessage(
        "inform", "TEST-3", {"note": "Contact alice@example.com"}, sender="Worker-Investigate",
        receiver=["Broker-Assign"])))

    assert stream_id == "1-0"
    assert [event.decision for event in audit.events] == ["publish_authorized", "published"]


def test_in_memory_bus_returns_recent_messages_oldest_first():
    async def run():
        bus = InMemoryBus(maxlen=2)
        for index in range(3):
            await bus.publish(ACLMessage("inform", f"T-{index}", {"n": index}))
        return await bus.recent(10)

    rows = asyncio.run(run())
    assert [row["correlation_id"] for row in rows] == ["T-1", "T-2"]  # bounded, oldest dropped
    assert all(row["occurred_at"] for row in rows)


def test_redis_history_is_chronological():
    class Redis:
        async def xrevrange(self, stream, count):
            assert stream == "t2d:messages" and count == 2
            return [("2000-0", {"message": '{"message_id":"second"}'}),
                    ("1000-0", {"message": '{"message_id":"first"}'})]

    bus = RedisStreamBus("redis://unused")
    bus._client = Redis()
    messages = asyncio.run(bus.recent(2))
    assert [item["message_id"] for item in messages] == ["first", "second"]
    assert messages[0]["occurred_at"] == "1970-01-01T00:00:01+00:00"
