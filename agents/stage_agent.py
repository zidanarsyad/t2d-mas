"""The shape every agent shares: perceive -> remember -> reason -> act -> report.

These are the five components of an intelligent agent from the report (section
5.3.1). Each stage agent fills in the five steps; `run()` calls them in order and
packs the result into one envelope, so the dashboard can show, for every agent,
what it saw, what it recalled, how it decided, what it did and what it reported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.policy import Policy


@dataclass
class Step:
    """One step's result: data for the next step, plus a plain-language note for people."""
    data: Any = None
    note: str = ""


@dataclass
class StageContext:
    ticket: dict[str, Any]                    # the ticket record (already masked)
    outputs: dict[str, dict[str, Any]]        # earlier stages' results: the shared blackboard
    policy: Policy
    seed: int                                 # derived from the ticket id, so runs are repeatable
    deps: Any                                 # repository, messages, mobile runtime, nodes, models
    guidance: dict[str, Any] | None = None    # a reviewer's interpreted change request, if any
    revision: int = 0
    tools_used: list[dict[str, Any]] = field(default_factory=list)

    def use_tool(self, tool: str, simulated: bool, detail: str = "") -> None:
        self.tools_used.append({"tool": tool, "simulated": simulated, "detail": detail})


class StageAgent:
    stage = ""
    agent_id = ""
    family = ""            # Scout, Broker, Worker or Security (the report's archetypes)
    mobility = "STATIC"
    execution_mode = "simulated"   # live | mixed | simulated
    simulation_note: str | None = None

    async def perceive(self, ctx: StageContext) -> Step:
        raise NotImplementedError

    async def remember(self, ctx: StageContext, seen: Step) -> Step:
        return Step(None, "Nothing to recall for this step.")

    async def reason(self, ctx: StageContext, seen: Step, memory: Step) -> Step:
        raise NotImplementedError

    async def act(self, ctx: StageContext, seen: Step, memory: Step, plan: Step) -> Step:
        return Step(None, "No tool call needed.")

    def report(self, ctx: StageContext, seen: Step, memory: Step, plan: Step, result: Step) -> dict[str, Any]:
        """Return the stage's fields, a one-line `summary` and optional gate `decisions`."""
        raise NotImplementedError

    def identity(self, ctx: StageContext) -> str:
        return self.agent_id

    async def run(self, ctx: StageContext) -> dict[str, Any]:
        seen = await self.perceive(ctx)
        memory = await self.remember(ctx, seen)
        plan = await self.reason(ctx, seen, memory)
        result = await self.act(ctx, seen, memory, plan)
        fields = self.report(ctx, seen, memory, plan, result)
        summary = fields.pop("summary")
        decisions = fields.pop("decisions", [])
        return {
            "stage": self.stage, "agent": self.identity(ctx), "family": self.family,
            "mobility": self.mobility, "execution_mode": self.execution_mode,
            "simulated": self.execution_mode == "simulated", "simulation_note": self.simulation_note,
            "seed": ctx.seed, "revision": ctx.revision, "summary": summary,
            "components": {"perceive": seen.note, "remember": memory.note, "reason": plan.note,
                           "act": result.note, "report": summary},
            "tools_used": ctx.tools_used, "decisions": decisions,
            **({"reviewer_guidance": ctx.guidance} if ctx.guidance else {}),
            **fields,
        }


def decision(gate: str, autonomous: bool, reason: str, policy: Policy, **inputs: Any) -> dict[str, Any]:
    """A gate result as stored in the stage output and the audit log."""
    return {"gate": gate, "autonomous": autonomous, "reason": reason, "inputs": inputs,
            "policy_id": policy.policy_id}
