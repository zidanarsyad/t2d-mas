# T2D-MAS agents (the backend)

The orchestrator API and the nine agents that move a piece of user feedback from intake to a
monitored release. Every agent follows the same five steps: **perceive → remember → reason →
act → report**. Every message, gate decision and approval goes into an append-only audit log.
See [AGENT_CATALOG.md](AGENT_CATALOG.md) for what each agent does and what is real or simulated.

## Run it

**Without Docker (local mode).** After the one-time setup in the
[main README](../README.md#run-it-no-docker-needed), one command from the repository root (on
macOS or Linux, write `.venv/bin/python`):

```powershell
.venv\Scripts\python -m uvicorn agents.app:app --port 8000
```

Local mode keeps tickets and the audit log in memory, uses an in-memory message bus, and runs
the six data nodes inside the same process. Each node runs the same signing, sandbox and egress
code as in Docker. `GET /health` tells you which parts are local. Everything is lost when you stop the server.

**With Docker.** Run `docker compose up --build`. This starts:
- the orchestrator;
- six resource-limited node containers;
- Redis Streams;
- PostgreSQL, which gets its schema from `data/schema.sql` the first time.

After a schema change, recreate the database volume once with `docker compose down -v`.

**Tests** (pytest comes with `agents/requirements.txt`):

```powershell
.venv\Scripts\python -m pytest agents/tests -q
```

The tests always run in local mode. They never use a real OpenRouter key, even if `.env` holds one.

## Code map

| File | What it holds |
|---|---|
| `app.py` | Builds the API, chooses local or Docker mode, `/health`, `/policy` |
| `routes_tickets.py` | Feedback inbox, create/advance/review a ticket |
| `routes_live.py` | Live events (SSE), message history, the mobile-agent demo |
| `routes_monitoring.py` | Simulated telemetry; an anomaly becomes a follow-up ticket |
| `routes_results.py` | A0–A3 evaluation runs and saved ticket histories |
| `pipeline.py` | Runs the agents in order, applies their gates, keeps each ticket's record |
| `reviews.py` | What a person can do at each gate, and what happens next |
| `stage_agent.py` | The shared five-step agent shape |
| `scouts.py` / `brokers.py` / `workers.py` | The nine agents, grouped as in the report |
| `security_policy.py` | Security-Policy checks: autonomy gate, secret scan, signed bundles, egress allowlist |
| `orchestrator.py` | The nine-stage state machine with blocking human gates |
| `policy.py` | Every threshold in one place (also served at `GET /policy`) |
| `feedback_samples.py` | Mock user feedback in Indonesian and English (demo only) |
| `text.py`, `similarity.py` | Feedback normalization; TF-IDF cosine duplicate search |
| `tools.py` | Seeded simulated tools: observability, project board, repository, CI, deploy |
| `node_runtime.py`, `scout_log_program.py`, `mobility.py` | Data nodes, the code a mobile agent carries, signing |
| `messaging.py`, `bus.py`, `events.py`, `audit.py`, `repository.py` | Messages, event stream, audit log, storage |
| `synthetic_data.py` | Evaluation tickets. Do not change: the report's numbers depend on them |

## API in brief

| Route | Purpose |
|---|---|
| `GET /feedback/inbox?seed=42&count=8&scenario=all\|flash_sale` | Mock user messages (no hidden answers) |
| `POST /sandbox/tickets` | Start a ticket from `{"feedback_id": "FB-001"}` or `{"body": "...", "title": "..."}`. Optional demo switches: `inject_test_secret`, `simulate_regression` |
| `POST /sandbox/tickets/{id}/advance` | Run the current stage's agent and move on, or stop at a gate |
| `POST /sandbox/tickets/{id}/review` | `{"approver", "approved", "intent": "accept\|request_changes\|reject", "reason"}` |
| `GET /sandbox/tickets`, `GET /sandbox/tickets/{id}` | Ticket snapshots with every agent's output |
| `GET /events` | Server-sent events (`stage.*`, `gate.evaluated`, `message.published`, `agent.migrated`, …) |
| `GET /messages/history` | Recent agent messages, oldest first |
| `POST /demo/migrate/{1-6}` | Send Scout-Log to one node and show the migration rule and byte counts |
| `GET /monitoring/telemetry`, `POST /monitoring/anomalies/{id}/ticket` | Monitoring view and its feedback loop |
| `GET /policy`, `GET /health` | Thresholds and gate table; which parts run locally |
| `GET /experiments`, `GET /history`, `GET /ticket-history` | Evaluation results and saved runs |

## Guardrails

These enforce the project's four rules.

**No merge or full deploy without a person.**
- The orchestrator always stops after QA (`pr_merge`) and after deployment (`release_signoff`).
- `execute_irreversible` runs the merge or release only if that gate was approved by a named person.
- The database trigger, or its in-memory twin, refuses a merged change or a production deployment without `human_approved = TRUE`.

**Append-only audit log.**
- Agent outputs, gate decisions, messages (before and after sending), approvals and blocked actions are all appended.
- Database triggers reject `UPDATE`, `DELETE` and `TRUNCATE` on `audit_log`.

**Raw data stays on the nodes.**
- Each node keeps its own (simulated) logs.
- Scout-Log either runs signed code next to them or asks the node's exporter.
- Only allowlisted aggregate fields can leave.
- The node logs contain fake customer e-mails, and a test checks they never appear outside.

**Reproducible numbers.**
- The simulated tools are seeded from the ticket id.
- The evaluation harness still reproduces the run the report cites (`python -m eval.compare_runs`).

## Optional OpenRouter (free models only)

Broker-Triage uses local keyword rules by default; these rules include Indonesian cues. If `OPENROUTER_API_KEY` is set, it also asks a free OpenRouter model.

**Which models it sends:**
- Only ids ending in `:free` are sent. Any other configured id is ignored and the reason is recorded.
- The defaults are `qwen/qwen3.8-27b:free`, then `inclusionai/ling-3.0-flash-sante:free`.

**How model answers are handled:**
- Model answers are capped below τ, so a person always reviews them.
- A rate limit (HTTP 429) falls back to the rules, which go through the normal autonomy gate.
- Masked ticket text and review notes leave the machine only when a key is configured.

This is a teaching prototype, not a production isolation boundary. Bundles run as arbitrary Python inside the node container, with time and memory limits. Do not expose these services to untrusted users or networks.
