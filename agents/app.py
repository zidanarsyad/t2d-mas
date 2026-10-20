"""The T2D-MAS orchestrator API.

Run it without Docker:  python -m uvicorn agents.app:app --port 8000

Without DATABASE_URL, REDIS_URL or NODE_URLS it starts in local mode: memory
storage, an in-memory message bus, six in-process data nodes and a signing key
that lives only in this process. GET /health says which parts are local, so the
dashboard can label them. Docker Compose sets all three and runs the real services.
"""
from __future__ import annotations

import base64
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agents import routes_live, routes_monitoring, routes_results, routes_tickets, tools
from agents.audit import MemoryAuditSink, PostgresAuditSink
from agents.bus import InMemoryBus, RedisStreamBus
from agents.events import EventHub
from agents.logging_config import configure_logging
from agents.mobility import MobileAgentRuntime
from agents.node_runtime import create_node_app
from agents.pipeline import Conflict, Deps, InvalidInput, Node, NotFound, TicketPipeline
from agents.policy import DEFAULT_POLICY, policy_from_row
from agents.repository import GuardViolation, MemoryRepository, PostgresRepository
from agents.severity_triage import _openrouter_models

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    database_url: str | None = None
    redis_url: str | None = None
    node_urls: list[str] = field(default_factory=list)
    private_key_dir: Path | None = None
    public_key_dir: Path | None = None
    results_dir: Path = REPO_ROOT / "results"

    @classmethod
    def from_env(cls) -> "Settings":
        def path(name: str) -> Path | None:
            return Path(os.environ[name]) if os.getenv(name) else None
        return cls(database_url=os.getenv("DATABASE_URL") or None, redis_url=os.getenv("REDIS_URL") or None,
                   node_urls=[url.strip() for url in os.getenv("NODE_URLS", "").split(",") if url.strip()],
                   private_key_dir=path("PRIVATE_KEY_DIR"), public_key_dir=path("PUBLIC_KEY_DIR"),
                   results_dir=path("RESULTS_DIR") or REPO_ROOT / "results")


def load_keys(settings: Settings) -> tuple[Any, Any, str]:
    """Ed25519 key pair for signing agent bundles; nodes only ever get the public half."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if settings.private_key_dir is None:
        private = Ed25519PrivateKey.generate()
        return private, private.public_key(), "in-memory key for this process"
    settings.private_key_dir.mkdir(parents=True, exist_ok=True)
    private_file = settings.private_key_dir / "agent_private.key"
    if private_file.exists():
        private = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_file.read_text()))
    else:
        private = Ed25519PrivateKey.generate()
        private_file.write_text(base64.b64encode(private.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())).decode())
        private_file.chmod(0o600)
    if settings.public_key_dir is not None:
        settings.public_key_dir.mkdir(parents=True, exist_ok=True)
        (settings.public_key_dir / "agent_public.key").write_text(base64.b64encode(private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())
    return private, private.public_key(), f"key files in {settings.private_key_dir}"


def open_storage(settings: Settings) -> tuple[Any, Any, dict[str, str]]:
    if settings.database_url:
        repository = PostgresRepository(settings.database_url)
        repository.check_connection()  # fail loudly: a configured database must be reachable
        return PostgresAuditSink(settings.database_url), repository, {"kind": "postgres", "detail": "DATABASE_URL"}
    audit = MemoryAuditSink()
    return audit, MemoryRepository(audit), {"kind": "memory", "detail": "DATABASE_URL is not set; data is lost on restart"}


async def open_bus(settings: Settings) -> tuple[Any, dict[str, str]]:
    if settings.redis_url:
        bus = RedisStreamBus(settings.redis_url)
        try:
            await bus.connect()
            return bus, {"kind": "redis", "detail": settings.redis_url.split("@")[-1]}
        except Exception as exc:
            return InMemoryBus(), {"kind": "memory", "detail": f"Redis unreachable ({type(exc).__name__})"}
    return InMemoryBus(), {"kind": "memory", "detail": "REDIS_URL is not set"}


async def open_nodes(settings: Settings, public_key: Any) -> tuple[list[Node], str]:
    """Use the node containers when configured and reachable; otherwise run them in-process."""
    import httpx

    nodes: list[Node] = []
    urls = settings.node_urls or [""] * len(tools.NODE_SERVICE)
    for index, (node_id, service) in enumerate(tools.NODE_SERVICE.items()):
        url = urls[index] if index < len(urls) else ""
        if url:
            try:
                async with httpx.AsyncClient(timeout=1.0) as client:
                    (await client.get(url.rstrip("/") + "/health")).raise_for_status()
                nodes.append(Node(node_id, service, url.rstrip("/"), None, "http"))
                continue
            except Exception:
                pass  # fall back to an in-process node for this one
        app = create_node_app(node_id, public_key)
        nodes.append(Node(node_id, service, f"http://{node_id}.local", httpx.ASGITransport(app=app), "in_process"))
    kinds = {node.kind for node in nodes}
    return nodes, "http" if kinds == {"http"} else "in_process" if kinds == {"in_process"} else "mixed"


def create_app(settings: Settings | None = None, **overrides: Any) -> FastAPI:
    """Build the API. `overrides` replace pipeline dependencies in tests (e.g. classify=...)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        active = settings or Settings.from_env()
        private, public, key_detail = load_keys(active)
        audit, repository, storage = open_storage(active)
        repository.ensure_seed(DEFAULT_POLICY, tools.DEFAULT_SLO_BASELINES)
        policy = policy_from_row(repository.load_policy())
        bus, bus_info = await open_bus(active)
        nodes, node_kind = await open_nodes(active, public)
        events = EventHub()
        pipeline = TicketPipeline(Deps(audit=audit, repository=repository, bus=bus, events=events,
                                       mobile=MobileAgentRuntime(private, public, audit), nodes=nodes,
                                       policy=policy, **overrides))
        local = [storage["kind"] == "memory", bus_info["kind"] == "memory", node_kind != "http"]
        app.state.settings, app.state.events, app.state.bus, app.state.pipeline = active, events, bus, pipeline
        app.state.health = {
            "status": "ok", "mode": "local" if all(local) else "docker" if not any(local) else "mixed",
            "storage": storage, "bus": bus_info, "signing_key": key_detail,
            "nodes": {"kind": node_kind, "items": [{"node_id": node.node_id, "service": node.service,
                                                    "transport": node.kind} for node in nodes]},
            "triage_llm": {"enabled": bool(os.getenv("OPENROUTER_API_KEY", "").strip()),
                           "models": _openrouter_models()[0]},
            "policy": {"policy_id": policy.policy_id, "source": policy.source}}
        yield
        await bus.close()

    app = FastAPI(title="T2D-MAS Orchestrator", lifespan=lifespan)
    for error, status in ((NotFound, 404), (Conflict, 409), (GuardViolation, 409), (InvalidInput, 422)):
        app.add_exception_handler(error, _error_handler(status))
    for module in (routes_tickets, routes_live, routes_monitoring, routes_results):
        app.include_router(module.router)

    @app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        return request.app.state.health

    @app.get("/policy")
    def policy(request: Request) -> dict[str, Any]:
        """Every threshold the agents use, plus the plain-language gate table."""
        return request.app.state.pipeline.policy.to_api()

    return app


def _error_handler(status: int):
    async def handle(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"detail": str(exc)})
    return handle


app = create_app()
