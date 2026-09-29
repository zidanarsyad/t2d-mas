"""Pure action guard so the deployment invariant is testable without Gymnasium."""
from __future__ import annotations


CANARY_ACTIONS = ("hold", "canary_5", "canary_25", "full")


def authorize_deployment_action(action: int | str, human_approved: bool) -> tuple[str, bool]:
    """Return (executed action, was blocked); full requires explicit human approval."""
    if isinstance(action, str):
        if action not in CANARY_ACTIONS:
            raise ValueError(f"unknown canary action: {action}")
        requested = action
    else:
        if not 0 <= int(action) < len(CANARY_ACTIONS):
            raise ValueError(f"action must be in [0, {len(CANARY_ACTIONS) - 1}]")
        requested = CANARY_ACTIONS[int(action)]
    if requested == "full" and not human_approved:
        return "hold", True
    return requested, False
