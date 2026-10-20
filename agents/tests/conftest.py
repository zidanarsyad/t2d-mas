"""Shared test setup: every test runs in local mode with no network, database or API key."""
import asyncio
import itertools

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agents import tools
from agents.app import Settings, open_nodes
from agents.audit import MemoryAuditSink
from agents.bus import InMemoryBus
from agents.events import EventHub
from agents.mobility import MobileAgentRuntime
from agents.pipeline import Deps, TicketPipeline
from agents.policy import DEFAULT_POLICY
from agents.repository import MemoryRepository

# A real .env may hold an OpenRouter key; tests must never use it or reach a real service.
ENVIRONMENT = ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_FALLBACK_MODEL", "DATABASE_URL",
               "REDIS_URL", "NODE_URLS", "PRIVATE_KEY_DIR", "PUBLIC_KEY_DIR", "RESULTS_DIR")


@pytest.fixture(autouse=True)
def local_mode(monkeypatch):
    for name in ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)


class CountingBus(InMemoryBus):
    """The in-memory bus, counting how many messages were published."""

    def __init__(self):
        super().__init__()
        self.count = 0

    async def publish(self, message):
        self.count += 1
        return await super().publish(message)


@pytest.fixture
def make_pipeline():
    """Build a fresh pipeline with in-memory storage, bus and six in-process nodes."""
    def build(**overrides):
        key = Ed25519PrivateKey.generate()
        audit = MemoryAuditSink()
        repository = MemoryRepository(audit)
        repository.ensure_seed(DEFAULT_POLICY, tools.DEFAULT_SLO_BASELINES)
        nodes, _kind = asyncio.run(open_nodes(Settings(), key.public_key()))
        counter = itertools.count(1)
        deps = Deps(audit=audit, repository=repository, bus=CountingBus(), events=EventHub(),
                    mobile=MobileAgentRuntime(key, key.public_key(), audit), nodes=nodes, policy=DEFAULT_POLICY,
                    new_ticket_id=lambda: f"TEST-{next(counter):04d}", **overrides)
        return TicketPipeline(deps)
    return build
