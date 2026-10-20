"""Human reviews: what a person can do at each gate, and what happens next.

At every pause a reviewer can approve, request changes or reject; a reason is
always required. Approving a merge or a full release runs that irreversible action
through the orchestrator, which first checks that the approval was recorded.
"""
from __future__ import annotations

from typing import Any

from agents.audit import AuditEvent
from agents.orchestrator import PipelinePaused
from agents.pii import mask_text, mask_value
from agents.pipeline import GATE_NEXT_STAGE, GATE_STAGE, Conflict, InvalidInput, TicketPipeline, now
from agents.workers import run_canary

INTENTS = {"accept", "request_changes", "reject"}
NEXT_AGENT_AFTER = {"autonomy_gate": "Broker-Assign", "secret_scan": "Worker-QA", "pr_merge": "Worker-Deploy",
                    "canary_review": "Worker-Deploy", "release_signoff": "Scout-Monitor"}


def allowed_intents(record: dict[str, Any], gate: str | None) -> set[str]:
    """A leaked secret, or a failed canary, can be fixed or stopped but never approved."""
    if gate == "secret_scan":
        return {"request_changes", "reject"}
    canary = record["_outputs"].get("deployment", {}).get("canary", {})
    if gate == "release_signoff" and canary.get("status") == "rolled_back":
        return {"request_changes", "reject"}
    return set(INTENTS)


async def handle_review(pipeline: TicketPipeline, ticket_id: str, approver: str, approved: bool,
                        intent: str | None, reason: str) -> dict[str, Any]:
    approver, reason = (approver or "").strip(), (reason or "").strip()
    if not approver or len(reason) < 3:
        raise InvalidInput("A reviewer name and a short reason are required.")
    record = pipeline._record(ticket_id)
    if pipeline._status(ticket_id) != "waiting_for_review":
        raise Conflict("This ticket is not waiting for a human review.")
    gate = pipeline.orchestrator.runs[ticket_id].waiting_for
    note = mask_text(reason)
    intent = intent or ("accept" if approved else "reject")
    if intent in {"accept", "reject"} and approved != (intent == "accept"):
        raise InvalidInput("The review intent and approval decision must agree.")
    if intent not in allowed_intents(record, gate):
        raise Conflict(f"\"{intent}\" is not possible at {gate}; request changes or reject instead.")
    if intent == "request_changes":
        return await _request_changes(pipeline, record, gate, approver, note)
    if intent == "reject":
        return await _reject(pipeline, record, gate, approver, note)
    return await _accept(pipeline, record, gate, approver, note)


async def _reject(pipeline: TicketPipeline, record: dict[str, Any], gate: str, approver: str, note: str) -> dict[str, Any]:
    ticket_id = record["ticket_id"]
    try:
        pipeline.orchestrator.approve(ticket_id, approver, False, note, "reject")
    except PipelinePaused:
        pass  # rejecting stops the run; the orchestrator signals that by pausing for good
    record["reviews"].append({"checkpoint": gate, "stage": GATE_STAGE.get(gate), "approver": approver,
                              "approved": False, "decision": "rejected", "intent": "reject", "note": note,
                              "interpretation": None, "next_stage": GATE_NEXT_STAGE.get(gate), "at": now()})
    record["review_requested_at"] = None
    pipeline.repository.update_ticket(ticket_id, status="rejected")
    await pipeline.messages.inform(ticket_id, approver, ["Orchestrator"],
                                   {"decision": "rejected", "checkpoint": gate, "intent": "reject", "note": note})
    await pipeline.emit("approval.resolved", ticket_id=ticket_id, approved=False, waiting_for="rejected",
                        checkpoint=gate, note=note)
    return pipeline.snapshot(ticket_id)


async def _accept(pipeline: TicketPipeline, record: dict[str, Any], gate: str, approver: str, note: str) -> dict[str, Any]:
    ticket_id = record["ticket_id"]
    next_stage = GATE_NEXT_STAGE.get(gate)
    interpretation = mask_value(await pipeline.interpret(note, next_stage or "next stage"))
    pipeline.orchestrator.approve(ticket_id, approver, True, note, "accept", interpretation, next_stage)
    record["reviews"].append({"checkpoint": gate, "stage": GATE_STAGE.get(gate), "approver": approver,
                              "approved": True, "decision": "accepted", "intent": "accept", "note": note,
                              "interpretation": interpretation, "next_stage": next_stage, "at": now()})
    record["review_requested_at"] = None
    await _on_approved(pipeline, record, gate, approver)
    await pipeline.emit("approval.resolved", ticket_id=ticket_id, approved=True, waiting_for=None,
                        checkpoint=gate, note=note)
    if gate == "duplicate_review":  # linked to the original; this run ends here
        return pipeline.snapshot(ticket_id)
    await pipeline.messages.inform(ticket_id, approver, [NEXT_AGENT_AFTER.get(gate, "Orchestrator")],
                                   {"decision": "accepted", "checkpoint": gate, "intent": "accept", "note": note,
                                    "interpretation": interpretation, "next_stage": next_stage})
    try:
        pipeline.orchestrator.resume_approved(ticket_id)
    except PipelinePaused:  # a second gate at the same stage (canary, then full release)
        await pipeline._paused(record)
        return pipeline.snapshot(ticket_id)
    await pipeline._advanced(record)
    return pipeline.snapshot(ticket_id)


async def _on_approved(pipeline: TicketPipeline, record: dict[str, Any], gate: str, approver: str) -> None:
    """Carry out what the approval allows: link, merge, start the canary or release."""
    ticket_id, outputs = record["ticket_id"], record["_outputs"]
    if gate == "duplicate_review":
        best = outputs["triage"]["duplicate"]["best_match"]
        await pipeline._close_as_duplicate(record, best["ticket_id"], best["cosine"], automatic=False)
    elif gate == "pr_merge":
        change_id = outputs["implementation"]["draft_pr"]["change_id"]
        await _irreversible(pipeline, record, "merge", approver,
                            lambda: pipeline.repository.mark_merged(change_id, approver, True))
    elif gate == "canary_review":
        deployment = outputs["deployment"]
        service = (outputs.get("investigation", {}).get("rca", {}) or {}).get("top_suspect") or "order-service"
        canary = run_canary(pipeline.context(record, "deployment"), service, deployment["risk_score"])
        deployment["canary"] = canary
        if canary["status"] == "rolled_back":
            deployment["full_release"]["status"] = "blocked"
            for item in deployment["decisions"]:
                if item["gate"] == "release_signoff":
                    item["reason"] = "canary_failed"
        pipeline.orchestrator.runs[ticket_id].pending_gates = pipeline._gates(deployment)
        pipeline.audit.append(AuditEvent(actor_id="Worker-Deploy", action="canary", decision=canary["status"],
                                         correlation_id=ticket_id, ticket_id=ticket_id, details=canary))
    elif gate == "release_signoff":
        deployment = outputs["deployment"]
        deployment_id = f"DEP-{ticket_id}-production"
        change_id = outputs["implementation"]["draft_pr"]["change_id"]
        executed = await _irreversible(pipeline, record, "full_deploy", approver, lambda: pipeline.repository.save_deployment({
            "deployment_id": deployment_id, "change_id": change_id, "ticket_id": ticket_id,
            "environment": "production", "strategy": "full", "risk_score": deployment["risk_score"],
            "status": "deployed", "human_approved": True, "approved_by": approver, "slo_breach": False}))
        if executed:
            deployment["full_release"] = {"status": "deployed", "deployment_id": deployment_id,
                                          "human_approved": True, "approved_by": approver}


async def _irreversible(pipeline: TicketPipeline, record: dict[str, Any], action: str, approver: str,
                        callback: Any) -> bool:
    ticket_id = record["ticket_id"]
    executed = pipeline.orchestrator.execute_irreversible(ticket_id, action, callback)
    record["irreversible_actions"].append({"action": action, "executed": executed, "human_approved": executed,
                                           "approver": approver, "at": now()})
    await pipeline.emit("action.executed" if executed else "action.blocked", ticket_id=ticket_id, action=action,
                        human_approved=executed, approver=approver,
                        reason="recorded human approval" if executed else "no recorded approval")
    return executed


async def _request_changes(pipeline: TicketPipeline, record: dict[str, Any], gate: str, approver: str,
                           note: str) -> dict[str, Any]:
    ticket_id, stage = record["ticket_id"], GATE_STAGE[gate]
    revision = 1 + sum(item.get("checkpoint") == gate and item.get("decision") == "changes_requested"
                       for item in record["reviews"])
    triage = None
    if gate == "autonomy_gate":
        text = f"{record['title']}\n{record['body']}"
        raw = {"summary": note, "requested_changes": [note], "constraints": [], "evidence": []}
        triage = await pipeline.classify(text, review_feedback=raw)
        interpretation = mask_value(triage.get("review_interpretation") or {
            **raw, "needs_clarification": False, "interpreter": "local feedback fallback",
            "fallback_reason": "Triage response did not include an interpretation"})
        # Without the model (no key, an error or a rate limit) only an explicit correction can be applied.
        if triage.get("provider") == "rules_fallback" and not triage.get("reviewer_override"):
            interpretation["needs_clarification"] = True
            interpretation["clarification_question"] = (
                "Triage could not interpret this change because OpenRouter is unavailable "
                f"({triage.get('fallback_reason', 'provider error')}). State an explicit severity correction "
                "(for example \"severity should be High\") or retry after the rate limit clears.")
    elif gate == "duplicate_review":
        interpretation = {"summary": note, "requested_changes": ["Treat this ticket as a new issue"],
                          "constraints": [], "evidence": [], "needs_clarification": False,
                          "interpreter": "duplicate review"}
    else:
        interpretation = mask_value(await pipeline.interpret(note, stage))
    review = {"checkpoint": gate, "stage": stage, "approver": approver, "approved": None,
              "decision": "changes_requested", "intent": "request_changes", "note": note,
              "interpretation": interpretation, "revision": revision, "at": now()}
    if interpretation.get("needs_clarification"):
        review["decision"] = "clarification_requested"
        record["reviews"].append(review)
        pipeline.audit.append(AuditEvent(actor_id=approver, action="human_review_feedback",
                                         decision="clarification_needed", correlation_id=ticket_id, ticket_id=ticket_id,
                                         details={"stage": stage, "checkpoint": gate, "intent": "request_changes",
                                                  "reason": note, "interpretation": interpretation,
                                                  "revision": revision}))
        await pipeline.emit("review.clarification_requested", ticket_id=ticket_id,
                            question=interpretation.get("clarification_question", "Please clarify the change."))
        return pipeline.snapshot(ticket_id)

    record["reviews"].append(review)
    await pipeline.messages.inform(ticket_id, approver, [pipeline._agent_for(record, stage)],
                                   {"decision": "request_changes", "checkpoint": gate, "stage": stage, "note": note,
                                    "interpretation": interpretation, "revision": revision})
    pipeline.orchestrator.request_revision(ticket_id, approver, note, interpretation)
    record["review_requested_at"] = None
    if gate == "duplicate_review":  # the reviewer says it is a new issue: keep going as one
        record["duplicate_override"] = "new"
        revised = record["_outputs"]["triage"]
        revised["duplicate"] = {**revised["duplicate"], "band": "new", "reviewer_override": "new"}
        for item in revised["decisions"]:
            if item["gate"] == "duplicate_review":
                item.update(autonomous=True, reason="reviewer_marked_new")
    else:
        record["_guidance"][stage] = interpretation
        record["_revisions"][stage] = record["_revisions"].get(stage, 0) + 1
        if triage is not None:
            record["_precomputed_triage"] = triage
        if gate == "secret_scan":  # redraft without the leaked value
            record["options"]["inject_test_secret"] = False
        revised = await pipeline._run_stage(record, stage)
    await pipeline._handoff(record, stage, revised)
    await pipeline.emit("approval.resolved", ticket_id=ticket_id, approved=None, intent="request_changes",
                        waiting_for=None, checkpoint=gate, note=note, interpretation=interpretation)
    return pipeline.snapshot(ticket_id)

