"""Signed mobile-agent bundles sent to resource-limited node runtimes."""
from __future__ import annotations

import base64
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from agents.audit import AuditEvent, AuditSink
from agents.security_policy import SecurityError, sign_bundle, validate_egress, verify_bundle_signature


@dataclass
class AgentBundle:
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
    """Follow the report's break-even policy: migrate when L_node > (A + R) * 3."""
    return node_log_mb > (agent_mb + result_mb) * factor


class MobileAgentRuntime:
    """Submit a signed agent bundle to a node and retrieve only allowlisted aggregates."""

    def __init__(self, private_key: Any, public_key: Any, audit_sink: AuditSink,
                 timeout_s: float = 30.0) -> None:
        self.private_key = private_key
        self.public_key = public_key
        self.timeout_s = timeout_s
        self.audit_sink = audit_sink
        self.stats = MigrationStats()

    async def migrate(self, node_url: str, agent_id: str, code: str,
                      state: dict[str, Any], correlation_id: str = "mobile-migration") -> dict[str, Any]:
        import httpx

        bundle = AgentBundle.create(agent_id, code, state, self.private_key)
        encoded = serialize_bundle(bundle)
        self.stats.bytes_sent += len(encoded)
        self.audit_sink.append(AuditEvent(actor_id=agent_id, action="mobile_migration",
            decision="authorized_to_execute", correlation_id=correlation_id,
            details={"bundle_id": bundle.bundle_id, "bytes_sent": len(encoded)}))
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            response = await client.post(node_url.rstrip("/") + "/execute", content=encoded,
                                         headers={"content-type": "application/json"})
            response.raise_for_status()
            result = response.json()
        if not verify_bundle_signature(bundle.payload(), bundle.signature, self.public_key):
            raise SecurityError("locally generated bundle did not verify")
        aggregate = validate_egress(result["result"])
        returned = json.dumps(aggregate, sort_keys=True, separators=(",", ":")).encode()
        self.stats.bytes_returned += len(returned)
        self.audit_sink.append(AuditEvent(actor_id=agent_id, action="mobile_migration",
            decision="completed", correlation_id=correlation_id,
            details={"bundle_id": bundle.bundle_id, "bytes_sent": len(encoded),
                     "bytes_returned": len(returned), "egress_fields": sorted(aggregate)}))
        return aggregate
