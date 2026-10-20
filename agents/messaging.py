"""Publish agent messages the auditable way: mask, audit, publish, audit again, notify the UI."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agents.audit import AuditEvent, AuditSink
from agents.bus import ACLMessage
from agents.events import EventHub
from agents.pii import mask_value

CONTRACT_NET = {"cfp", "propose", "accept-proposal", "reject-proposal"}


class MessageService:
    """One entry point for every ACL message, so no message skips the audit log.

    It also has a `publish(message)` method, so the Contract Net broker can use it
    directly as its message bus.
    """

    def __init__(self, bus: Any, audit: AuditSink, events: EventHub) -> None:
        self.bus = bus
        self.audit = audit
        self.events = events

    async def publish(self, message: ACLMessage) -> str:
        if message.performative in CONTRACT_NET:
            message.content.setdefault("stage", "assignment")
        message.content = mask_value(message.content)
        message.policy_context = mask_value(message.policy_context)
        details = mask_value({"message_id": message.message_id, "sender": message.sender,
                              "receivers": message.receiver, "performative": message.performative,
                              "content": message.content, "policy_context": message.policy_context,
                              "ontology": message.ontology})
        # Record the intent before the side effect: if the audit store fails, nothing is sent.
        self.audit.append(AuditEvent(actor_id=message.sender, action="agent_message",
                                     decision="publish_authorized", correlation_id=message.correlation_id,
                                     ticket_id=message.correlation_id, details=details))
        stream_id = await self.bus.publish(message)
        self.audit.append(AuditEvent(actor_id=message.sender, action="agent_message", decision="published",
                                     correlation_id=message.correlation_id, ticket_id=message.correlation_id,
                                     details={**details, "stream_id": stream_id}))
        await self.events.publish({
            "type": "message.published", "correlation_id": message.correlation_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(), "message_id": message.message_id,
            "performative": message.performative, "sender": message.sender, "receiver": message.receiver,
            "content": message.content, "policy_context": message.policy_context, "ontology": message.ontology})
        return stream_id

    async def inform(self, ticket_id: str, sender: str, receivers: list[str],
                     content: dict[str, Any], policy_context: dict[str, Any] | None = None) -> str:
        """Send a plain handoff ("here is my result") from one agent to the next."""
        return await self.publish(ACLMessage("inform", ticket_id, content, policy_context or {},
                                             sender=sender, receiver=receivers))
