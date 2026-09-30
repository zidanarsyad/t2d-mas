"""FastAPI orchestrator API: health, approval queue, and a mobile-node demo route."""
from __future__ import annotations

import base64
import asyncio
import csv
import json
import os
from dataclasses import asdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from agents.audit import AuditEvent, PostgresAuditSink
from agents.bus import ACLMessage, RedisStreamBus
from agents.broker_assign import ContractNetBroker
from agents.events import event_hub
from agents.logging_config import configure_logging
from agents.mobility import MobileAgentRuntime
from agents.orchestrator import T2DOrchestrator
from agents.orchestrator import PipelinePaused, STAGES
from agents.pii import mask_text, mask_value
from agents.security_policy import evaluate_gate
from agents.severity_triage import classify_ticket_with_llm, interpret_review_feedback
from agents.synthetic_data import make_synthetic_tickets, synthetic_review_note
from agents.workflow_agents import HANDOFF_TARGETS, STAGE_AGENT_IDS, assignment_proposals, prototype_stage_output

configure_logging()
PRIVATE_KEY_DIR = Path(os.getenv("PRIVATE_KEY_DIR", "/run/t2d/private"))
PUBLIC_KEY_DIR = Path(os.getenv("PUBLIC_KEY_DIR", "/run/t2d/public"))
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", "/app/results"))


def _result_runs() -> list[Path]:
    if not RESULTS_DIR.is_dir():
        return []
    return sorted(
        (path for path in RESULTS_DIR.iterdir() if path.is_dir() and (path / "summary.csv").is_file()),
        key=lambda path: path.name,
        reverse=True,
    )


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
MANUAL_STAGE_AGENTS = {
    "intake": "Scout-Feedback",
    "triage": "Broker-Triage",
    "assignment": "Broker-Assign",
    "investigation": "Worker-Investigate",
    "planning": "Worker-Plan",
    "implementation": "Worker-Impl",
    "qa": "Worker-QA",
    "deployment": "Worker-Deploy",
    "monitoring": "Scout-Monitor",
}


def _save_ticket_record(ticket_id: str, title: str, body: str, severity: str,
                        source: str, dataset_version: str) -> None:
    """Persist ticket inputs so their audit records remain reviewable after restart."""
    import psycopg

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to save ticket history")
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """INSERT INTO tickets
               (ticket_id, source, title, body, severity, dataset_version, pii_masked)
               VALUES (%s, %s, %s, %s, %s, %s, TRUE)
               ON CONFLICT (ticket_id) DO NOTHING""",
            (ticket_id, source, title, body, severity, dataset_version),
        )


def _update_ticket_severity(ticket_id: str, severity: str) -> None:
    """Keep the searchable ticket row aligned with a reviewed triage revision."""
    import psycopg

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to update ticket history")
    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE tickets SET severity = %s WHERE ticket_id = %s",
                           (severity, ticket_id))


def _record_manual_stage_activity(ticket_id: str, record: dict[str, Any], stage: str,
                                  output_override: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist one inspectable agent result for each stage in the course prototype."""
    completed = record.setdefault("_recorded_stages", set())
    if stage in completed:
        return record.setdefault("_agent_outputs", {}).get(stage, {})
    agent_id = MANUAL_STAGE_AGENTS[stage]
    if stage == "intake":
        output = {"normalized_title": record["title"], "description_characters": len(record["body"]),
                  "source": "manual sandbox"}
    elif stage == "triage":
        output = {"severity": record["severity"], "rule_score": record["severity_confidence"],
                  "rationale": record["severity_rationale"], "matched_cues": record["severity_cues"],
                  "provider": record.get("severity_provider", "rules")}
        guidance = record.get("_review_guidance", {}).get(stage)
        if guidance:
            output["reviewer_guidance"] = guidance
            output["revision"] = sum(
                item.get("intent") == "request_changes" and item.get("stage") == stage
                for item in record.get("reviews", []))
        if record.get("severity_provider") == "openrouter":
            output["model"] = record.get("severity_model")
    else:
        output = output_override or prototype_stage_output(stage, record)
    decision = "completed"
    execution_mode = {
        "intake": "input_normalization",
        "triage": "rule_based_prototype" if record.get("severity_provider") != "openrouter" else "optional_llm_proposal",
        "assignment": "contract_net_prototype",
        "investigation": "keyword_hypothesis_only",
        "planning": "template_prototype",
        "implementation": "draft_only_no_repository_access",
        "qa": "checklist_only_no_ci_runner",
        "deployment": "simulation_only",
        "monitoring": "placeholder_without_telemetry",
    }[stage]
    app.state.audit.append(AuditEvent(
        actor_id=agent_id,
        action="agent_output",
        decision=decision,
        correlation_id=ticket_id,
        ticket_id=ticket_id,
        details={"stage": stage, "execution_mode": execution_mode,
                 "output": output},
    ))
    completed.add(stage)
    record.setdefault("_agent_outputs", {})[stage] = output
    return output


class _ObservableMessageBus:
    """Route Contract Net ACL traffic through the auditable live-message endpoint."""

    async def publish(self, message: ACLMessage) -> str:
        response = await publish_message(asdict(message))
        return response["stream_id"]


async def _run_contract_net(ticket_id: str, record: dict[str, Any]) -> dict[str, Any]:
    proposals = {proposal.worker_id: proposal for proposal in assignment_proposals(record)}

    async def bid(worker_id: str, task: dict[str, Any]):
        proposal = proposals[worker_id]
        await publish_message({
            "performative": "propose", "correlation_id": ticket_id,
            "sender": worker_id, "receiver": ["Broker-Assign"],
            "policy_context": {"tau": 0.70, "risk_max": 0.60},
            "content": {"worker_id": worker_id, "skill": proposal.skill,
                        "load": proposal.load, "cost": proposal.cost,
                        "utility": proposal.score, "task": task.get("task")},
        })
        return proposal

    broker = ContractNetBroker(_ObservableMessageBus(), bid, app.state.audit)
    winner = await broker.assign({"ticket_id": ticket_id, "severity": record["severity"],
                                  "task": "Select a capable worker for the next pipeline stage"},
                                 list(proposals))
    return {"winner": winner.worker_id, "utility": winner.score,
            "bids": [{"worker_id": proposal.worker_id, "skill": proposal.skill,
                      "load": proposal.load, "cost": proposal.cost, "utility": proposal.score}
                     for proposal in sorted(proposals.values(), key=lambda item: item.worker_id)],
            "method": "Contract Net utility = 0.5 skill + 0.3 (1 - load) + 0.2 (1 - cost)"}


async def _publish_stage_handoff(ticket_id: str, stage: str, output: dict[str, Any],
                                 recipient: str | None = None) -> None:
    """Emit the actual stage handoff as an ACL message and a live dashboard event."""
    agent_id = STAGE_AGENT_IDS.get(stage, stage)
    target = recipient or HANDOFF_TARGETS[stage]
    await publish_message({
        "performative": "inform", "correlation_id": ticket_id,
        "sender": agent_id, "receiver": [target],
        "content": {"stage": stage, "summary": f"{agent_id} handed off its {stage} result",
                    "output": output},
    })


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    PRIVATE_KEY_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_KEY_DIR.mkdir(parents=True, exist_ok=True)
    private_file = PRIVATE_KEY_DIR / "agent_private.key"
    public_file = PUBLIC_KEY_DIR / "agent_public.key"
    if private_file.exists():
        private = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_file.read_text()))
    else:
        private = Ed25519PrivateKey.generate()
        private_file.write_text(base64.b64encode(private.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
            serialization.NoEncryption())).decode())
        private_file.chmod(0o600)
    public_file.write_text(base64.b64encode(private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())
    app.state.audit = PostgresAuditSink()
    app.state.pipeline = T2DOrchestrator(app.state.audit)
    app.state.manual_ticket_records = {}
    app.state.bus = RedisStreamBus(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    await app.state.bus.connect()
    await app.state.bus.ensure_group("workers")
    app.state.mobile = MobileAgentRuntime(private, private.public_key(), audit_sink=app.state.audit)
    yield
    await app.state.bus.close()


app = FastAPI(title="T2D-MAS Orchestrator", lifespan=lifespan)


class StartTicket(BaseModel):
    ticket_id: str
    title: str = ""
    body: str = ""
    severity: Literal["Low", "Medium", "High", "Critical", "Unknown"] = "Unknown"


class Approval(BaseModel):
    approver: str
    approved: bool
    reason: str = ""


class ManualTicket(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    body: str = Field(min_length=10, max_length=4000)


class ManualReview(BaseModel):
    approver: str = Field(min_length=1, max_length=80)
    approved: bool
    intent: Literal["accept", "request_changes", "reject"] | None = None
    reason: str = Field(min_length=3, max_length=500)


def _manual_ticket_snapshot(ticket_id: str) -> dict[str, Any]:
    record = app.state.manual_ticket_records.get(ticket_id)
    run = app.state.pipeline.runs.get(ticket_id)
    if record is None or run is None:
        raise HTTPException(status_code=404, detail="Manual test ticket not found.")
    if run.waiting_for == "rejected":
        status = "rejected"
    elif run.waiting_for:
        status = "waiting_for_review"
    elif run.completed:
        status = "completed"
    else:
        status = "running"
    completed = {item["from"] for item in run.history}
    if run.completed:
        completed.add(run.stage.value)
    return {
        **{key: value for key, value in record.items() if not key.startswith("_")},
        "agent_outputs": record.get("_agent_outputs", {}),
        "status": status,
        "current_stage": run.stage.value,
        "waiting_for": run.waiting_for,
        "stages": [{"name": stage.value,
                    "status": "completed" if stage.value in completed else
                              "rejected" if status == "rejected" and stage == run.stage else
                              "current" if stage == run.stage and status not in {"rejected", "completed"} else
                              "upcoming"}
                   for stage in STAGES],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "orchestrator"}


@app.get("/experiments")
def experiments() -> dict[str, Any]:
    runs = []
    for directory in _result_runs():
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


@app.get("/history")
def ticket_history(
    run_id: str | None = None,
    severity: str = "Low,Medium,High,Critical",
    seed: str = "all",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=50),
) -> dict[str, Any]:
    available = _result_runs()
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


@app.get("/ticket-history")
def saved_ticket_history(limit: Annotated[int, Query(ge=1, le=50)] = 50) -> dict[str, Any]:
    """Return persisted sandbox tickets with timestamped audit events and agent outputs."""
    import psycopg

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is required to read saved ticket history.")
    try:
        with psycopg.connect(database_url) as connection:
            rows = connection.execute(
                """SELECT ticket_id, title, body, severity,
                          (SELECT MIN(occurred_at) FROM audit_log WHERE audit_log.ticket_id = tickets.ticket_id)
                   FROM tickets
                   WHERE EXISTS (SELECT 1 FROM audit_log WHERE audit_log.ticket_id = tickets.ticket_id)
                   ORDER BY created_on DESC, ticket_id DESC LIMIT %s""", (limit,),
            ).fetchall()
            ids = [row[0] for row in rows]
            audit_rows = connection.execute(
                """SELECT occurred_at, actor_id, action, decision, details
                   FROM audit_log WHERE ticket_id = ANY(%s)
                   ORDER BY occurred_at, audit_id""", (ids,),
            ).fetchall() if ids else []
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not read saved ticket history: {exc}") from exc

    by_ticket: dict[str, list[dict[str, Any]]] = {ticket_id: [] for ticket_id in ids}
    for occurred_at, actor_id, action, decision, wrapped_details in audit_rows:
        envelope = wrapped_details if isinstance(wrapped_details, dict) else {}
        details = envelope.get("details", envelope)
        ticket_id = envelope.get("ticket_id")
        if ticket_id in by_ticket:
            by_ticket[ticket_id].append({
                "occurred_at": occurred_at.isoformat() if hasattr(occurred_at, "isoformat") else str(occurred_at),
                "agent": actor_id,
                "action": action,
                "decision": decision,
                "stage": details.get("stage") if isinstance(details, dict) else None,
                "execution_mode": details.get("execution_mode") if isinstance(details, dict) else None,
                "output": (details.get("output") or details.get("result") or details.get("proposal") or
                           details.get("content")) if isinstance(details, dict) else None,
                "message_id": details.get("message_id") if isinstance(details, dict) else None,
                "receivers": details.get("receivers") if isinstance(details, dict) else None,
                "performative": details.get("performative") if isinstance(details, dict) else None,
                "checkpoint": details.get("checkpoint") if isinstance(details, dict) else None,
                "approver": details.get("approver") if isinstance(details, dict) else None,
                "note": details.get("reason") if isinstance(details, dict) else None,
                "intent": details.get("intent") if isinstance(details, dict) else None,
                "interpretation": details.get("interpretation") if isinstance(details, dict) else None,
                "revision": details.get("revision") if isinstance(details, dict) else None,
                "next_stage": details.get("next_stage") if isinstance(details, dict) else None,
            })
    items = [{
        "ticket_id": row[0], "title": row[1], "body": row[2], "severity": row[3],
        "process_started_at": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
        "events": by_ticket.get(row[0], []),
    } for row in rows]
    return {"total": len(items), "limit": limit, "items": items}


@app.get("/events")
async def events() -> StreamingResponse:
    async def stream():
        yield "event: ready\ndata: {\"status\":\"connected\"}\n\n"
        iterator = event_hub.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(anext(iterator), timeout=20)
                    yield f"event: update\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            await iterator.aclose()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@app.post("/tickets")
async def start_ticket(body: StartTicket) -> dict[str, Any]:
    title, description = mask_text(body.title.strip()), mask_text(body.body.strip())
    _save_ticket_record(body.ticket_id, title, description, body.severity,
                        "pipeline", "pipeline-v1")
    run = app.state.pipeline.start(body.ticket_id)
    await event_hub.publish({"type": "ticket.started", "ticket_id": run.ticket_id,
                             "stage": run.stage.value, "title": title,
                             "severity": body.severity})
    return {"ticket_id": run.ticket_id, "stage": run.stage.value}


@app.post("/sandbox/tickets")
async def start_manual_ticket(body: ManualTicket) -> dict[str, Any]:
    ticket_id = f"TEST-{uuid4().hex[:8].upper()}"
    normalized_title, normalized_body = mask_text(body.title.strip()), mask_text(body.body.strip())
    triage = await classify_ticket_with_llm(f"{normalized_title}\n{normalized_body}")
    _save_ticket_record(ticket_id, normalized_title, normalized_body, triage["severity"],
                        "sandbox", "manual-sandbox-v1")
    app.state.pipeline.start(ticket_id)
    app.state.manual_ticket_records[ticket_id] = {
        "ticket_id": ticket_id,
        "title": normalized_title,
        "body": normalized_body,
        "severity": triage["severity"],
        "severity_confidence": triage["confidence"],
        "severity_rationale": triage["rationale"],
        "severity_agent": triage["agent"],
        "severity_provider": triage.get("provider", "rules"),
        "severity_model": triage.get("model"),
        "severity_cues": triage["matched_cues"],
        "component": "Manual test",
        "reviews": [],
        "_recorded_stages": set(),
        "_agent_outputs": {},
        "_policy_recorded": False,
    }
    record = app.state.manual_ticket_records[ticket_id]
    intake_output = _record_manual_stage_activity(ticket_id, record, "intake")
    await _publish_stage_handoff(ticket_id, "intake", intake_output)
    triage_output = _record_manual_stage_activity(ticket_id, record, "triage")
    await _publish_stage_handoff(ticket_id, "triage", triage_output)
    await event_hub.publish({"type": "ticket.started", "ticket_id": ticket_id,
                             "stage": "intake", "title": normalized_title,
                             "severity": triage["severity"]})
    return _manual_ticket_snapshot(ticket_id)


@app.get("/sandbox/tickets/{ticket_id}")
def get_manual_ticket(ticket_id: str) -> dict[str, Any]:
    return _manual_ticket_snapshot(ticket_id)


@app.post("/sandbox/tickets/{ticket_id}/advance")
async def advance_manual_ticket(ticket_id: str) -> dict[str, Any]:
    snapshot = _manual_ticket_snapshot(ticket_id)
    if snapshot["status"] in {"rejected", "completed"}:
        raise HTTPException(status_code=409, detail=f"Ticket test is {snapshot['status']}.")
    try:
        record = app.state.manual_ticket_records[ticket_id]
        stage = app.state.pipeline.runs[ticket_id].stage.value
        if stage not in record["_recorded_stages"]:
            stage_output = await _run_contract_net(ticket_id, record) if stage == "assignment" else None
            stage_output = _record_manual_stage_activity(ticket_id, record, stage, stage_output)
            if stage != "triage":
                await _publish_stage_handoff(ticket_id, stage, stage_output)
        decision = None
        if stage == "triage":
            decision = evaluate_gate(record["severity_confidence"], record["severity"])
            if not record["_policy_recorded"]:
                app.state.audit.append(AuditEvent(
                    actor_id="Security-Policy", action="policy_gate",
                    decision="autonomous" if decision.autonomous else "escalated",
                    correlation_id=ticket_id, ticket_id=ticket_id,
                    confidence=record["severity_confidence"],
                    details={"stage": "triage", "severity": record["severity"],
                             "risk": decision.risk, "reason": decision.reason,
                             "tau": 0.70, "risk_max": 0.60},
                ))
                record["_policy_recorded"] = True
            await _publish_stage_handoff(
                ticket_id, "triage",
                {"decision": "autonomous" if decision.autonomous else "escalated",
                 "risk": decision.risk, "reason": decision.reason,
                 "severity": record["severity"]},
                "Broker-Assign" if decision.autonomous else "Human-Reviewer",
            )
        run = app.state.pipeline.advance(ticket_id, decision=decision)
    except PipelinePaused:
        run = app.state.pipeline.runs[ticket_id]
        pending = run.approval_queue[-1] if run.approval_queue else None
        await event_hub.publish({"type": "approval.requested", "ticket_id": ticket_id,
                                 "checkpoint": pending["checkpoint"] if pending else run.waiting_for,
                                 "reason": pending["reason"] if pending else "Human review required"})
        return _manual_ticket_snapshot(ticket_id)
    await event_hub.publish({"type": "pipeline.advanced", "ticket_id": ticket_id,
                             "stage": run.stage.value})
    if run.completed:
        await event_hub.publish({"type": "pipeline.completed", "ticket_id": ticket_id})
    return _manual_ticket_snapshot(ticket_id)


@app.post("/sandbox/tickets/{ticket_id}/review")
async def review_manual_ticket(ticket_id: str, body: ManualReview) -> dict[str, Any]:
    snapshot = _manual_ticket_snapshot(ticket_id)
    if snapshot["status"] != "waiting_for_review":
        raise HTTPException(status_code=409, detail="This ticket is not waiting for human review.")
    record = app.state.manual_ticket_records[ticket_id]
    safe_note = mask_text(body.reason.strip())
    intent = body.intent or ("accept" if body.approved else "reject")
    if intent == "request_changes":
        checkpoint = snapshot["waiting_for"]
        stage = {"autonomy_gate": "triage", "pr_merge": "qa",
                 "release_signoff": "deployment"}.get(checkpoint)
        if stage is None:
            raise HTTPException(status_code=409, detail="No revisable agent is assigned to this checkpoint.")
        interpretation = mask_value(await interpret_review_feedback(safe_note, stage))
        revision = sum(item.get("intent") == "request_changes" and item.get("checkpoint") == checkpoint
                       for item in record["reviews"]) + 1
        review = {"checkpoint": checkpoint, "stage": stage,
                  "approver": body.approver.strip(), "approved": None,
                  "decision": "changes_requested", "intent": intent,
                  "note": safe_note, "interpretation": interpretation, "revision": revision}
        if interpretation.get("needs_clarification"):
            review["decision"] = "clarification_requested"
            record["reviews"].append(review)
            app.state.audit.append(AuditEvent(
                actor_id=review["approver"], action="human_review_feedback",
                decision="clarification_needed", correlation_id=ticket_id, ticket_id=ticket_id,
                details={"stage": stage, "checkpoint": checkpoint, "intent": intent,
                         "reason": safe_note, "interpretation": interpretation,
                         "revision": revision},
            ))
            await event_hub.publish({"type": "review.clarification_requested", "ticket_id": ticket_id,
                                     "question": interpretation.get("clarification_question", "Please clarify the requested change.")})
            return _manual_ticket_snapshot(ticket_id)

        record["reviews"].append(review)
        record.setdefault("_review_guidance", {})[stage] = interpretation
        await publish_message({
            "performative": "inform", "correlation_id": ticket_id,
            "sender": review["approver"], "receiver": [STAGE_AGENT_IDS[stage]],
            "content": {"decision": intent, "checkpoint": checkpoint, "stage": stage,
                        "note": safe_note, "interpretation": interpretation,
                        "revision": revision},
        })
        app.state.pipeline.request_revision(ticket_id, review["approver"], safe_note, interpretation)
        if stage == "triage":
            ticket_text = f"{record['title']}\n{record['body']}"
            try:
                triage = await classify_ticket_with_llm(ticket_text, review_feedback=interpretation)
            except TypeError:  # Keep compatible with simple test/demo classifier adapters.
                triage = await classify_ticket_with_llm(ticket_text)
            record.update({
                "severity": triage["severity"],
                "severity_confidence": triage["confidence"],
                "severity_rationale": triage["rationale"],
                "severity_agent": triage["agent"],
                "severity_provider": triage.get("provider", "rules"),
                "severity_model": triage.get("model"),
                "severity_cues": triage["matched_cues"],
            })
            _update_ticket_severity(ticket_id, record["severity"])
            record.setdefault("_recorded_stages", set()).discard(stage)
            revised_output = _record_manual_stage_activity(ticket_id, record, "triage")
        else:
            revised_output = prototype_stage_output(stage, record)
            requested = interpretation.get("requested_changes", [])
            if stage == "qa":
                revised_output["recommended_checks"] = list(dict.fromkeys(
                    [*revised_output.get("recommended_checks", []), *requested]))
            revised_output["reviewer_guidance"] = interpretation
            revised_output["revision"] = revision
            revised_output["revision_status"] = "prototype_updated_no_external_execution"
            record.setdefault("_recorded_stages", set()).discard(stage)
            revised_output = _record_manual_stage_activity(ticket_id, record, stage, revised_output)
        await _publish_stage_handoff(ticket_id, stage, revised_output)
        await event_hub.publish({"type": "approval.resolved", "ticket_id": ticket_id,
                                 "approved": None, "intent": intent, "waiting_for": None,
                                 "note": safe_note, "interpretation": interpretation})
        return _manual_ticket_snapshot(ticket_id)

    next_stage_by_checkpoint = {"autonomy_gate": "assignment", "pr_merge": "deployment",
                                "release_signoff": "monitoring"}
    next_stage = next_stage_by_checkpoint.get(snapshot["waiting_for"])
    interpretation = mask_value(await interpret_review_feedback(safe_note, next_stage or "next stage")) \
        if body.approved else None
    review = {"checkpoint": snapshot["waiting_for"], "approver": body.approver.strip(),
              "approved": body.approved, "decision": "accepted" if body.approved else "rejected",
              "intent": intent,
              "note": safe_note, "interpretation": interpretation, "next_stage": next_stage}
    try:
        app.state.pipeline.approve(ticket_id, review["approver"], body.approved, safe_note, intent,
                                    interpretation, next_stage)
    except PipelinePaused:
        if body.approved:
            raise
        record["reviews"].append(review)
        await publish_message({
            "performative": "inform", "correlation_id": ticket_id,
            "sender": review["approver"], "receiver": ["Orchestrator"],
            "content": {"decision": "rejected", "checkpoint": review["checkpoint"],
                        "intent": intent, "note": safe_note},
        })
        await event_hub.publish({"type": "approval.resolved", "ticket_id": ticket_id,
                                 "approved": False, "waiting_for": "rejected",
                                 "note": review["note"]})
        return _manual_ticket_snapshot(ticket_id)
    record["reviews"].append(review)
    next_agent = {"autonomy_gate": "Broker-Assign", "pr_merge": "Worker-Deploy",
                  "release_signoff": "Scout-Monitor"}.get(review["checkpoint"], "Orchestrator")
    await publish_message({
        "performative": "inform", "correlation_id": ticket_id,
        "sender": review["approver"], "receiver": [next_agent],
        "content": {"decision": "accepted", "checkpoint": review["checkpoint"],
                    "intent": intent, "note": safe_note,
                    "interpretation": interpretation, "next_stage": next_stage},
    })
    run = app.state.pipeline.resume_approved(ticket_id)
    await event_hub.publish({"type": "approval.resolved", "ticket_id": ticket_id,
                             "approved": True, "waiting_for": None, "note": review["note"]})
    await event_hub.publish({"type": "pipeline.advanced", "ticket_id": ticket_id,
                             "stage": run.stage.value})
    return _manual_ticket_snapshot(ticket_id)


@app.get("/approvals")
def approvals() -> list[dict[str, Any]]:
    return [item for run in app.state.pipeline.runs.values() for item in run.approval_queue]


@app.post("/messages")
async def publish_message(body: dict[str, Any]) -> dict[str, str]:
    try:
        message = ACLMessage(**body)
        message.content = mask_value(message.content)
        message.policy_context = mask_value(message.policy_context)
        message_details = mask_value({"message_id": message.message_id,
                                      "sender": message.sender, "receivers": message.receiver,
                                      "performative": message.performative,
                                      "content": message.content,
                                      "policy_context": message.policy_context,
                                      "ontology": message.ontology})
        # Persist the intent before the Redis side effect; no message is sent if audit is unavailable.
        app.state.audit.append(AuditEvent(
            actor_id=message.sender, action="agent_message", decision="publish_authorized",
            correlation_id=message.correlation_id, ticket_id=message.correlation_id,
            details=message_details,
        ))
        stream_id = await app.state.bus.publish(message)
        app.state.audit.append(AuditEvent(
            actor_id=message.sender, action="agent_message", decision="published",
            correlation_id=message.correlation_id, ticket_id=message.correlation_id,
            details={**message_details, "stream_id": stream_id},
        ))
        await event_hub.publish({"type": "message.published", "correlation_id": message.correlation_id,
                                 "message_id": message.message_id, "performative": message.performative,
                                 "sender": message.sender, "receiver": message.receiver,
                                 "content": message.content, "policy_context": message.policy_context,
                                 "ontology": message.ontology})
        return {"stream_id": stream_id, "message_id": message.message_id}
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/messages/next")
async def read_message(consumer: str) -> list[dict[str, Any]]:
    messages = await app.state.bus.read_group("workers", consumer, count=5, block_ms=250)
    return [{"stream_id": item_id, "message": message.__dict__} for item_id, message in messages]


@app.post("/messages/{entry_id}/ack")
async def acknowledge_message(entry_id: str) -> dict[str, int]:
    return {"acknowledged": await app.state.bus.ack("workers", entry_id)}


@app.post("/tickets/{ticket_id}/approve")
async def approve(ticket_id: str, body: Approval) -> dict[str, Any]:
    try:
        run = app.state.pipeline.approve(ticket_id, body.approver, body.approved,
                                         mask_text(body.reason))
        await event_hub.publish({"type": "approval.resolved", "ticket_id": run.ticket_id,
                                 "approved": body.approved, "waiting_for": run.waiting_for})
        return {"ticket_id": run.ticket_id, "waiting_for": run.waiting_for,
                "human_approved": run.human_approved}
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/tickets/{ticket_id}/resume")
async def resume(ticket_id: str) -> dict[str, Any]:
    try:
        run = app.state.pipeline.resume_approved(ticket_id)
        await event_hub.publish({"type": "pipeline.advanced", "ticket_id": run.ticket_id,
                                 "stage": run.stage.value})
        return {"ticket_id": run.ticket_id, "stage": run.stage.value}
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/demo/migrate/{node_id}")
async def demo_migrate(node_id: int) -> dict[str, Any]:
    if not 1 <= node_id <= 6:
        raise HTTPException(status_code=404, detail="node_id must be 1..6")
    nodes = os.getenv("NODE_URLS", "").split(",")
    if len(nodes) != 6 or not nodes[node_id - 1]:
        raise HTTPException(status_code=503, detail="node runtime URLs are not configured")
    code = """import json, sys
state = json.load(sys.stdin)
print(json.dumps({key: state[key] for key in (
    'service', 'request_count', 'error_rate', 'latency_p95_ms', 'evidence_hash'
)}))
"""
    state = {"service": f"service-{node_id}", "request_count": 1200 + node_id,
             "error_rate": 0.01 * node_id, "latency_p95_ms": 100 + node_id,
             "evidence_hash": f"demo-aggregate-{node_id}"}
    try:
        result = await app.state.mobile.migrate(nodes[node_id - 1], "Scout-Log", code, state,
                                                correlation_id=f"mobile-node-{node_id}")
        await event_hub.publish({"type": "agent.migrated", "agent_id": "Scout-Log",
                                 "node_id": node_id, "bytes_sent": app.state.mobile.stats.bytes_sent,
                                 "bytes_returned": app.state.mobile.stats.bytes_returned})
        return {"node_id": node_id, "result": result,
                "bytes_sent": app.state.mobile.stats.bytes_sent,
                "bytes_returned": app.state.mobile.stats.bytes_returned}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
