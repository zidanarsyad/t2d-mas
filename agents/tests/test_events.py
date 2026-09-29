import asyncio

from agents.events import EventHub


def test_sse_event_hub_fans_out_and_cleans_up():
    async def scenario():
        hub = EventHub(queue_size=2)
        stream = hub.subscribe()
        waiting = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        await hub.publish({"type": "pipeline.advanced", "ticket_id": "T-1"})
        assert await waiting == {"type": "pipeline.advanced", "ticket_id": "T-1"}
        await stream.aclose()
        assert not hub._subscribers

    asyncio.run(scenario())
