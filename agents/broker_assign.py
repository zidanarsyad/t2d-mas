"""Contract Net Protocol assignment for worker agents."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable

from agents.audit import AuditEvent, AuditSink
from agents.bus import ACLMessage, RedisStreamBus


def utility(skill: float, load: float, cost: float) -> float:
    """Score a normalized bid using the report's 0.5/0.3/0.2 weights."""
    if any(not 0.0 <= x <= 1.0 for x in (skill, load, cost)):
        raise ValueError("skill, load, and cost must be normalized to [0, 1]")
    return 0.5 * skill + 0.3 * (1.0 - load) + 0.2 * (1.0 - cost)


@dataclass(frozen=True)
class Proposal:
    worker_id: str
    skill: float
    load: float
    cost: float

    @property
    def score(self) -> float:
        return utility(self.skill, self.load, self.cost)


async def select_winner(proposals: Iterable[Proposal]) -> tuple[Proposal, list[Proposal]]:
    """Return the highest-utility proposal and all remaining proposals as rejects."""
    ordered = sorted(proposals, key=lambda bid: (-bid.score, bid.worker_id))
    if not ordered:
        raise ValueError("no proposals received before deadline")
    return ordered[0], ordered[1:]


class ContractNetBroker:
    """Publishes CFPs, gathers bids until deadline, then sends accept/reject messages."""

    def __init__(self, bus: RedisStreamBus,
                 bidder: Callable[[str, dict[str, Any]], Awaitable[Proposal | None]],
                 audit_sink: AuditSink) -> None:
        self.bus = bus
        self.bidder = bidder
        self.audit_sink = audit_sink

    async def assign(self, task: dict[str, Any], workers: list[str],
                     deadline_s: float = 2.0) -> Proposal:
        correlation_id = str(task["ticket_id"])
        # Write audit intent before publishing so an audit-store failure fails closed.
        self.audit_sink.append(AuditEvent(actor_id="broker-assign", action="contract_net",
            decision="cfp_authorized", correlation_id=correlation_id,
            ticket_id=correlation_id, details={"workers": workers, "deadline_s": deadline_s}))
        cfp = ACLMessage("cfp", correlation_id, task, {"tau": 0.70, "risk_max": 0.60},
                         sender="broker-assign@orchestrator", receiver=workers)
        await self.bus.publish(cfp)
        bids: list[Proposal] = []
        pending = {asyncio.create_task(self.bidder(worker, task)) for worker in workers}
        loop = asyncio.get_running_loop()
        deadline = loop.time() + deadline_s
        while pending and loop.time() < deadline:
            done, pending = await asyncio.wait(pending, timeout=max(0.0, deadline - loop.time()),
                                               return_when=asyncio.FIRST_COMPLETED)
            for future in done:
                proposal = future.result()
                if proposal is not None:
                    bids.append(proposal)
        for future in pending:
            future.cancel()
        winner, rejects = await select_winner(bids)
        self.audit_sink.append(AuditEvent(actor_id="broker-assign", action="contract_net",
            decision="winner_selected", correlation_id=correlation_id,
            ticket_id=correlation_id, details={"worker_id": winner.worker_id,
                                               "utility": winner.score,
                                               "rejected": [bid.worker_id for bid in rejects]}))
        await self.bus.publish(ACLMessage("accept-proposal", correlation_id,
            {"worker_id": winner.worker_id, "utility": winner.score}, sender="broker-assign@orchestrator"))
        for proposal in rejects:
            await self.bus.publish(ACLMessage("reject-proposal", correlation_id,
                {"worker_id": proposal.worker_id, "utility": proposal.score}, sender="broker-assign@orchestrator"))
        return winner
