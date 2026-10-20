"""Small helpers shared by the pipeline tests."""

FINISHED = {"completed", "rejected", "duplicate"}


def fixed_triage(severity="High", confidence=0.68, **extra):
    """A stand-in classifier that always returns the same result."""
    async def classify(_text, review_feedback=None):
        return {"severity": severity, "confidence": confidence, "matched_cues": ["stub"],
                "rationale": f"Stub classifier: {severity}.", "agent": "stub", "provider": "rules", **extra}
    return classify


async def interpret_as_given(note, _stage):
    return {"summary": note, "requested_changes": [note], "constraints": [], "evidence": [],
            "needs_clarification": False, "interpreter": "test"}


def accept_when_possible(snapshot):
    return "accept" if "accept" in snapshot["pending_gate"]["allowed_intents"] else "request_changes"


async def walk(pipeline, ticket_id, decide=accept_when_possible, approver="reviewer", limit=40):
    """Advance a ticket until it finishes, answering every gate with `decide(snapshot)`."""
    snapshot = pipeline.snapshot(ticket_id)
    seen_gates = []
    for _ in range(limit):
        if snapshot["status"] in FINISHED:
            return snapshot, seen_gates
        if snapshot["status"] == "waiting_for_review":
            seen_gates.append(snapshot["waiting_for"])
            intent = decide(snapshot)
            snapshot = await pipeline.review(ticket_id, approver, intent == "accept", intent,
                                             f"{intent} at {snapshot['waiting_for']}")
        else:
            snapshot = await pipeline.advance(ticket_id)
    raise AssertionError(f"ticket {ticket_id} did not finish: {snapshot['status']} at {snapshot['current_stage']}")
