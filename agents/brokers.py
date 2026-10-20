"""Broker agents: they decide where a ticket goes.

- Broker-Triage judges severity, looks for duplicates and applies the autonomy gate.
- Broker-Assign runs a Contract Net auction so the best-placed squad takes the ticket.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from agents.broker_assign import ContractNetBroker, Proposal
from agents.bus import ACLMessage
from agents.policy import duplicate_band, sla_due
from agents.security_policy import RISK_BY_CLASS, evaluate_gate
from agents.stage_agent import StageAgent, StageContext, Step, decision

# Three investigation squads and how well each knows each product area (0..1).
SQUADS = {
    "Worker-Investigate-Payments": {"squad": "Payments", "cost": 0.30,
                                    "skills": {"payment": 0.92, "promo": 0.80, "delivery": 0.55, "account": 0.45}},
    "Worker-Investigate-Mobile": {"squad": "Mobile app", "cost": 0.25,
                                  "skills": {"login": 0.90, "account": 0.82, "notification": 0.80, "app": 0.88}},
    "Worker-Investigate-Platform": {"squad": "Platform", "cost": 0.35,
                                    "skills": {"search": 0.90, "delivery": 0.78, "app": 0.70, "payment": 0.60}},
}
DEFAULT_SKILL = 0.5


class BrokerTriage(StageAgent):
    stage, agent_id, family, execution_mode = "triage", "Broker-Triage", "Broker", "live"

    async def perceive(self, ctx: StageContext) -> Step:
        text = f"{ctx.ticket['title']}\n{ctx.ticket['body']}"
        return Step(text, f"Read the normalized ticket \"{ctx.ticket['title']}\" ({ctx.ticket.get('component')}).")

    async def remember(self, ctx: StageContext, seen: Step) -> Step:
        # Only tickets reported before this one can be its original.
        earlier = [row for row in ctx.deps.repository.recent_ticket_texts()
                   if ctx.deps.reported_before(row["ticket_id"], ctx.ticket["ticket_id"])]
        return Step(earlier, f"Recalled {len(earlier)} earlier ticket(s) from the blackboard to compare against.")

    async def reason(self, ctx: StageContext, seen: Step, memory: Step) -> Step:
        candidates = [(row["ticket_id"], f"{row['title']}\n{row['body']}") for row in memory.data]
        ctx.use_tool("duplicate_index.search", simulated=False, detail="TF-IDF over character 3-5-grams, cosine")
        matches = ctx.deps.duplicates.best_matches(seen.data, candidates, top=3)
        best_id, best_score = matches[0] if matches else (None, 0.0)
        band = duplicate_band(best_score, ctx.policy)
        override = ctx.ticket.get("duplicate_override")
        if override == "new":  # a reviewer said "this is a new issue"
            band = "new"
        titles = {row["ticket_id"]: row["title"] for row in memory.data}
        duplicate = {"band": band, "best_match": ({"ticket_id": best_id, "title": titles.get(best_id),
                                                   "cosine": round(best_score, 3)} if best_id else None),
                     "candidates": [{"ticket_id": ticket_id, "cosine": round(score, 3)} for ticket_id, score in matches],
                     "compared_with": len(candidates), "method": "char 3-5-gram TF-IDF cosine",
                     "reviewer_override": override}
        ctx.use_tool("severity.classify", simulated=False,
                     detail="local impact rules; OpenRouter :free model when a key is set")
        # A reviewer's re-triage is classified once in agents/reviews.py and passed in here.
        severity = ctx.ticket.pop("_precomputed_triage", None) or await ctx.deps.classify(seen.data)
        note = (f"Closest earlier ticket: {best_id} (similarity {best_score:.2f}, band {band}). "
                if best_id else "No earlier tickets to compare. ")
        return Step({"duplicate": duplicate, "severity": severity},
                    note + f"Severity {severity['severity']} with confidence {severity['confidence']:.2f} "
                           f"({severity.get('provider', 'rules')}).")

    async def act(self, ctx: StageContext, seen: Step, memory: Step, plan: Step) -> Step:
        severity = plan.data["severity"]["severity"]
        ctx.use_tool("blackboard.update_ticket", simulated=False, detail="severity")
        ctx.deps.repository.update_ticket(ctx.ticket["ticket_id"], severity=severity)
        return Step(None, f"Recorded severity {severity} on the ticket.")

    def report(self, ctx, seen, memory, plan, result) -> dict[str, Any]:
        triage, duplicate = plan.data["severity"], plan.data["duplicate"]
        policy = ctx.policy
        gate = evaluate_gate(triage["confidence"], triage["severity"], policy.tau, policy.risk_max)
        best = duplicate["best_match"] or {}
        decisions = [
            decision("duplicate_review", duplicate["band"] != "review", duplicate["band"], policy,
                     cosine=best.get("cosine"), auto_link=policy.duplicate_auto_link, review=policy.duplicate_review),
            decision("autonomy_gate", gate.autonomous, gate.reason, policy, confidence=triage["confidence"],
                     tau=policy.tau, risk=RISK_BY_CLASS[triage["severity"]], risk_max=policy.risk_max),
        ]
        duplicate_text = {"auto_link": f"duplicate of {best.get('ticket_id')} ({best.get('cosine')})",
                          "review": f"possible duplicate of {best.get('ticket_id')} ({best.get('cosine')}), needs review",
                          "new": f"new issue (closest match {best['cosine']})" if best
                          else "new issue (no earlier tickets)"}[duplicate["band"]]
        fields = {key: triage.get(key) for key in (
            "severity", "confidence", "rationale", "matched_cues", "provider", "fallback_reason", "rate_limited",
            "model", "preferred_model", "fallback_used", "model_fallback_reason", "reviewer_override", "category")}
        return {**fields, "rule_score": triage["confidence"], "duplicate": duplicate, "decisions": decisions,
                "review_interpretation": triage.get("review_interpretation"),
                "summary": f"{triage['severity']} (confidence {triage['confidence']:.2f}); {duplicate_text}."}


class BrokerAssign(StageAgent):
    stage, agent_id, family, execution_mode = "assignment", "Broker-Assign", "Broker", "live"

    async def perceive(self, ctx: StageContext) -> Step:
        component = ctx.ticket.get("component", "other")
        return Step(component, f"Needs an investigator for a {ctx.ticket.get('severity')} {component} ticket.")

    async def remember(self, ctx: StageContext, seen: Step) -> Step:
        load = ctx.deps.squad_load(ctx.ticket["ticket_id"])
        return Step(load, "Checked each squad's skills and open tickets: "
                          + ", ".join(f"{SQUADS[worker]['squad']} {count} open" for worker, count in load.items()) + ".")

    async def reason(self, ctx: StageContext, seen: Step, memory: Step) -> Step:
        proposals = {worker: Proposal(worker, profile["skills"].get(seen.data, DEFAULT_SKILL),
                                      round(min(1.0, 0.1 + memory.data.get(worker, 0) / 4), 2), profile["cost"])
                     for worker, profile in SQUADS.items()}
        return Step(proposals, "Each squad bids with utility = 0.5·skill + 0.3·(1 − load) + 0.2·(1 − cost).")

    async def act(self, ctx: StageContext, seen: Step, memory: Step, plan: Step) -> Step:
        ticket_id, proposals = ctx.ticket["ticket_id"], plan.data

        async def bid(worker: str, task: dict[str, Any]) -> Proposal:
            proposal = proposals[worker]  # each squad answers the call for bids with its offer
            await ctx.deps.messages.publish(ACLMessage(
                "propose", ticket_id, {"worker_id": worker, "skill": proposal.skill, "load": proposal.load,
                                       "cost": proposal.cost, "utility": proposal.score, "task": task.get("task")},
                {"tau": ctx.policy.tau, "risk_max": ctx.policy.risk_max}, sender=worker,
                receiver=["Broker-Assign"]))
            return proposal

        ctx.use_tool("contract_net.auction", simulated=False, detail="cfp → propose → accept/reject")
        broker = ContractNetBroker(ctx.deps.messages, bid, ctx.deps.audit,
                                   policy_context={"tau": ctx.policy.tau, "risk_max": ctx.policy.risk_max})
        winner = await broker.assign({"ticket_id": ticket_id, "severity": ctx.ticket.get("severity"),
                                      "component": seen.data, "task": "Investigate this ticket"}, list(proposals))
        return Step(winner, f"{winner.worker_id} won the auction with utility {winner.score:.3f}.")

    def report(self, ctx, seen, memory, plan, result) -> dict[str, Any]:
        winner = result.data
        severity = ctx.ticket.get("severity", "Medium")
        bids = [{"worker_id": proposal.worker_id, "squad": SQUADS[proposal.worker_id]["squad"],
                 "skill": proposal.skill, "load": proposal.load, "cost": proposal.cost,
                 "utility": round(proposal.score, 3), "open_tickets": memory.data.get(proposal.worker_id, 0)}
                for proposal in sorted(plan.data.values(), key=lambda item: item.worker_id)]
        return {"winner": winner.worker_id, "squad": SQUADS[winner.worker_id]["squad"],
                "utility": round(winner.score, 3), "bids": bids,
                "method": "Contract Net utility = 0.5 skill + 0.3 (1 - load) + 0.2 (1 - cost)",
                "sla_hours": ctx.policy.sla_hours.get(severity, ctx.policy.sla_hours["Medium"]),
                "sla_due": sla_due(severity, datetime.fromisoformat(ctx.ticket["created_at"]), ctx.policy),
                "summary": f"Assigned to the {SQUADS[winner.worker_id]['squad']} squad "
                           f"(utility {winner.score:.3f}); SLA {ctx.policy.sla_hours.get(severity, 72)} hours."}
