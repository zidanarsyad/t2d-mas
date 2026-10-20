"""HTTP routes for saved results: the A0-A3 evaluation runs and saved ticket histories.

The evaluation numbers are produced by eval/runner.py (python -m eval.runner); these
routes only read the result folders and the saved audit history.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request

from agents.synthetic_data import make_synthetic_tickets, synthetic_review_note

router = APIRouter()


def _result_runs(results_dir: Path) -> list[Path]:
    if not results_dir.is_dir():
        return []
    return sorted((path for path in results_dir.iterdir() if path.is_dir() and (path / "summary.csv").is_file()),
                  key=lambda path: path.name, reverse=True)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _number(value: str | None, integer: bool = False) -> int | float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
        return int(numeric) if integer else numeric
    except (TypeError, ValueError):
        return None


def _truth(value: str | None) -> bool:
    return (value or "").lower() == "true"


HISTORY_SEVERITY_ORDER = ("Low", "Medium", "High", "Critical")
HISTORY_SEVERITY_WEIGHTS = {"Low": 53, "Medium": 31, "High": 11, "Critical": 5}


def _history_sample(tickets: list[dict[str, Any]], selected_severities: set[str]) -> list[dict[str, Any]]:
    """Choose a stable, severity-stratified window of at most fifty ticket records."""
    target_size = min(50, len(tickets))
    if target_size == 0:
        return []
    enabled = [severity for severity in HISTORY_SEVERITY_ORDER if severity in selected_severities]
    if not enabled:
        return []
    weight_total = sum(HISTORY_SEVERITY_WEIGHTS[item] for item in enabled)
    exact = {item: target_size * HISTORY_SEVERITY_WEIGHTS[item] / weight_total for item in enabled}
    quotas = {item: int(exact[item]) for item in enabled}
    if target_size == 50 and enabled == list(HISTORY_SEVERITY_ORDER):
        quotas = {"Low": 26, "Medium": 16, "High": 6, "Critical": 2}
    else:
        for item in sorted(enabled, key=lambda value: exact[value] - quotas[value], reverse=True)[:target_size - sum(quotas.values())]:
            quotas[item] += 1
    buckets = {item: [ticket for ticket in tickets if ticket["severity"] == item] for item in enabled}
    chosen: list[dict[str, Any]] = []
    for item in enabled:
        take = min(quotas[item], len(buckets[item]))
        chosen.extend(buckets[item][:take])
        buckets[item] = buckets[item][take:]
        quotas[item] -= take
    while len(chosen) < target_size:
        available = [item for item in enabled if buckets[item]]
        if not available:
            break
        item = max(available, key=lambda value: (quotas[value] > 0, HISTORY_SEVERITY_WEIGHTS[value]))
        chosen.append(buckets[item].pop(0))
        quotas[item] = max(0, quotas[item] - 1)
    return sorted(chosen, key=lambda row: (row["ticket_id"], row["seed"]))


@router.get("/experiments")
def experiments(request: Request) -> dict[str, Any]:
    runs = []
    for directory in _result_runs(request.app.state.settings.results_dir):
        metadata_path = directory / "metadata.json"
        config_path = directory / "config.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
        runs.append({
            "run_id": directory.name,
            "created_at_utc": metadata.get("created_at_utc", directory.name),
            "dataset_version": metadata.get("dataset_version", config.get("dataset_version", "unknown")),
            "measurement_note": metadata.get("measurement_note", config.get("notes", "")),
            "seeds": config.get("seeds", []),
            "tickets_per_seed": config.get("tickets_per_seed"),
            "arms": _read_csv(directory / "summary.csv"),
        })
    return {"runs": runs}


@router.get("/history")
def ticket_history(
    request: Request,
    run_id: str | None = None,
    severity: str = "Low,Medium,High,Critical",
    seed: str = "all",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=50),
) -> dict[str, Any]:
    available = _result_runs(request.app.state.settings.results_dir)
    if not available:
        raise HTTPException(status_code=404, detail="No saved evaluation results were found.")
    selected = next((path for path in available if path.name == run_id), None) if run_id else available[0]
    if selected is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found.")
    ticket_path, stage_path = selected / "per_ticket.csv", selected / "per_stage.csv"
    if not ticket_path.is_file() or not stage_path.is_file():
        raise HTTPException(status_code=404, detail="This run does not include ticket and stage history.")

    all_tickets = _read_csv(ticket_path)
    all_stages = _read_csv(stage_path)
    seeds = sorted({int(row["seed"]) for row in all_tickets if row.get("seed", "").isdigit()})
    all_seeds = seed.lower() == "all"
    try:
        selected_seed = None if all_seeds else int(seed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="seed must be All seeds or a listed seed value.") from exc
    if selected_seed is not None and selected_seed not in seeds:
        raise HTTPException(status_code=404, detail="Evaluation seed not found.")
    selected_severities = {item.strip().title() for item in severity.split(",") if item.strip()}
    if not selected_severities or not selected_severities.issubset({"Low", "Medium", "High", "Critical"}):
        raise HTTPException(status_code=422, detail="severity must contain Low, Medium, High, Critical, or a combination.")

    config_path = selected / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    ticket_count = int(config.get("tickets_per_seed", 100))
    ticket_text = {
        (ticket_seed, item["ticket_id"]): item
        for ticket_seed in seeds
        for item in make_synthetic_tickets(ticket_seed, ticket_count)
    }

    by_ticket: dict[str, dict[str, Any]] = {}
    for row in all_tickets:
        row_seed = int(row["seed"])
        if (selected_seed is not None and row_seed != selected_seed) or row["severity_actual"] not in selected_severities:
            continue
        ticket_id = row["ticket_id"]
        ticket_key = f"{row_seed}:{ticket_id}"
        ticket = by_ticket.setdefault(ticket_key, {
            "ticket_id": ticket_id,
            "seed": row_seed,
            "severity": row["severity_actual"],
            "duplicate_of": row.get("duplicate_of") or None,
            **{key: ticket_text.get((row_seed, ticket_id), {}).get(key, "")
               for key in ("title", "body", "component", "created_at")},
            "arms": {},
        })
        review_decision = row.get("review_decision") or (
            ("accepted" if _truth(row.get("human_approved")) else "rejected")
            if row["severity_actual"] in {"High", "Critical"} else "not_required"
        )
        review_note = row.get("review_note") or (
            synthetic_review_note(row["severity_actual"], _truth(row.get("human_approved")))
            if row["severity_actual"] in {"High", "Critical"} else ""
        )
        ticket["arms"][row["arm"]] = {
            "arm": row["arm"],
            "arm_description": row["arm_description"],
            "severity_predicted": row["severity_predicted"],
            "severity_confidence": _number(row.get("severity_confidence")),
            "deployment_success": _truth(row.get("deployment_success")),
            "rollback": _truth(row.get("rollback")),
            "human_approved": _truth(row.get("human_approved")),
            "review_decision": review_decision,
            "review_note": review_note,
            "lead_time_hours": _number(row.get("lead_time_hours_simulated")),
            "wall_time_seconds": _number(row.get("total_wall_time_s")),
            "network_bytes": _number(row.get("network_bytes"), integer=True),
            "messages": _number(row.get("messages"), integer=True),
            "duplicate_recall_at_5": _number(row.get("recall_at_5")),
            "stages": [],
        }

    stage_index: dict[tuple[int, str, str], list[dict[str, str]]] = {}
    selected_ticket_ids = {item["ticket_id"] for item in by_ticket.values()}
    for row in all_stages:
        row_seed = int(row["seed"])
        if (selected_seed is None or row_seed == selected_seed) and row["ticket_id"] in selected_ticket_ids:
            stage_index.setdefault((row_seed, row["ticket_id"], row["arm"]), []).append(row)
    arm_order = ["A0", "A1", "A2", "A3"]
    for ticket in by_ticket.values():
        ticket_id, ticket_seed = ticket["ticket_id"], ticket["seed"]
        for arm in arm_order:
            arm_data = ticket["arms"].get(arm)
            if arm_data is None:
                continue
            stage_rows = stage_index.get((ticket_seed, ticket_id, arm), [])
            arm_data["stages"] = [{
                "stage": row["stage"],
                "wall_time_seconds": _number(row.get("wall_time_s")),
                "network_bytes": _number(row.get("network_bytes"), integer=True),
                "messages": _number(row.get("messages"), integer=True),
                "llm_tokens_estimated": _number(row.get("llm_tokens_estimated"), integer=True),
            } for row in stage_rows]

    tickets = sorted(by_ticket.values(), key=lambda row: (row["ticket_id"], row["seed"]))
    matching_total = len(tickets)
    tickets = _history_sample(tickets, selected_severities)
    return {
        "run_id": selected.name,
        "dataset_version": next((row.get("dataset_version", "unknown") for row in all_tickets), "unknown"),
        "seed": "All seeds" if selected_seed is None else selected_seed,
        "seeds": seeds,
        "available_severities": ["Low", "Medium", "High", "Critical"],
        "total": len(tickets),
        "matching_total": matching_total,
        "severity_counts": {item: sum(ticket["severity"] == item for ticket in tickets)
                            for item in HISTORY_SEVERITY_ORDER},
        "offset": offset,
        "limit": limit,
        "items": tickets[offset:offset + limit],
    }


@router.get("/ticket-history")
def saved_ticket_history(request: Request, limit: Annotated[int, Query(ge=1, le=50)] = 50) -> dict[str, Any]:
    """Saved sandbox tickets with their timestamped audit events (Postgres, or memory in local mode)."""
    try:
        return request.app.state.pipeline.repository.ticket_history(limit)
    except Exception as exc:  # database down or schema missing
        raise HTTPException(status_code=503, detail=f"Could not read saved ticket history: {exc}") from exc
