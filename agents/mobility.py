"""Mobile agents: signed code bundles that travel to a data node and bring back aggregates."""
from __future__ import annotations

import base64
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from agents.audit import AuditEvent, AuditSink
from agents.security_policy import SecurityError, sign_bundle, validate_egress, verify_bundle_signature


@dataclass
class AgentBundle:
    # The field layout is part of the evaluation's byte counts; do not change it.
    bundle_id: str
    agent_id: str
    code_b64: str
    state: dict[str, Any]
    signature: str = ""

    def payload(self) -> bytes:
        """Canonical bytes make signatures reproducible across services."""
        body = {"bundle_id": self.bundle_id, "agent_id": self.agent_id,
                "code_b64": self.code_b64, "state": self.state}
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def create(cls, agent_id: str, code: str, state: dict[str, Any], private_key: Any) -> "AgentBundle":
        bundle = cls(str(uuid.uuid4()), agent_id, base64.b64encode(code.encode()).decode(), state)
        bundle.signature = sign_bundle(bundle.payload(), private_key)
        return bundle


def serialize_bundle(bundle: AgentBundle) -> bytes:
    """Return the compact JSON body submitted to the node runtime."""
    return json.dumps(asdict(bundle), sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass
class MigrationStats:
    bytes_sent: int = 0
    bytes_returned: int = 0


def should_migrate(node_log_mb: float, agent_mb: float, result_mb: float, factor: float = 3.0) -> bool:
    """The report's break-even rule: move the agent when L_node > (A + R) * factor.

    L_node is the node's log volume, A the agent bundle size and R the expected result
    size (all in MB). Below the threshold, shipping the agent costs more than it saves.
    """
    return node_log_mb > (agent_mb + result_mb) * factor


class MobileAgentRuntime:
    """Sign a bundle, send it to a node, and accept only allowlisted aggregates back."""

    def __init__(self, private_key: Any, public_key: Any, audit_sink: AuditSink,
                 timeout_s: float = 30.0) -> None:
        self.private_key = private_key
        self.public_key = public_key
        self.timeout_s = timeout_s
        self.audit_sink = audit_sink
        self.stats = MigrationStats()

    async def migrate(self, node_url: str, agent_id: str, code: str, state: dict[str, Any],
                      correlation_id: str = "mobile-migration", transport: Any = None) -> dict[str, Any]:
        """Run one trip and return {bundle_id, aggregate, bytes_sent, bytes_returned}."""
        import httpx

        bundle = AgentBundle.create(agent_id, code, state, self.private_key)
        # Check our own signature before anything leaves the orchestrator.
        if not verify_bundle_signature(bundle.payload(), bundle.signature, self.public_key):
            raise SecurityError("locally generated bundle did not verify")
        encoded = serialize_bundle(bundle)
        self.audit_sink.append(AuditEvent(actor_id=agent_id, action="mobile_migration",
            decision="authorized_to_execute", correlation_id=correlation_id, ticket_id=correlation_id,
            details={"bundle_id": bundle.bundle_id, "node": node_url, "bytes_sent": len(encoded)}))
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, transport=transport) as client:
                response = await client.post(node_url.rstrip("/") + "/execute", content=encoded,
                                             headers={"content-type": "application/json"})
                response.raise_for_status()
                aggregate = validate_egress(response.json()["result"])
        except Exception as exc:
            self.audit_sink.append(AuditEvent(actor_id=agent_id, action="mobile_migration", decision="failed",
                correlation_id=correlation_id, ticket_id=correlation_id,
                details={"bundle_id": bundle.bundle_id, "node": node_url, "error": str(exc)[:200]}))
            raise
        returned = json.dumps(aggregate, sort_keys=True, separators=(",", ":")).encode()
        self.stats.bytes_sent += len(encoded)
        self.stats.bytes_returned += len(returned)
        self.audit_sink.append(AuditEvent(actor_id=agent_id, action="mobile_migration", decision="completed",
            correlation_id=correlation_id, ticket_id=correlation_id,
            details={"bundle_id": bundle.bundle_id, "node": node_url, "bytes_sent": len(encoded),
                     "bytes_returned": len(returned), "egress_fields": sorted(aggregate)}))
        return {"bundle_id": bundle.bundle_id, "aggregate": aggregate,
                "bytes_sent": len(encoded), "bytes_returned": len(returned)}
