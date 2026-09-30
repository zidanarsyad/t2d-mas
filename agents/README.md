# T2D-MAS agents prototype

This course prototype provides an auditable agent interface, Redis Streams ACL-style messaging, Contract Net worker selection, signed mobile bundles, node APIs, and a nine-stage pipeline. See [AGENT_CATALOG.md](AGENT_CATALOG.md) for each agent's task, objective, capabilities, and implementation status.

## Run the checks

From the repository root:

```powershell
python -m pip install -r agents/requirements.txt
python -m pip install pytest
python -m pytest agents/tests -q
```

## Run the demo services

Docker Compose starts one orchestrator, six resource-limited node runtimes, Redis Streams, and PostgreSQL. The database schema is initialized from `data/schema.sql` on the first start of the Postgres volume.

```powershell
docker compose up --build
```

Try `GET http://localhost:8000/health`, then `POST http://localhost:8000/demo/migrate/1` to send a signed demonstration bundle to node 1. Redis messaging is exposed through `POST /messages`, `GET /messages/next?consumer=worker-1`, and `POST /messages/{stream_id}/ack`; published message payloads are masked and appended to the audit log before and after publication. `GET /approvals` shows pending human decisions. The web sandbox uses `POST /sandbox/tickets`; advance it through all nine stages, and its agent outputs, Contract Net bids, ACL handoffs, and review notes are stored in Postgres and reviewed through `GET /ticket-history` (latest 50 tickets with audit events). Agent conversations receives these handoffs over SSE and recovers recent messages through non-consuming `GET /messages/history`. Shared `GET /sandbox/tickets` snapshots preserve browser navigation and refresh; backend restarts retain audit history but not resumable state. The orchestrator stores its private signing key in a volume unavailable to node containers; nodes mount only the public key.

For the reproducible §8.5 flash-sale timeline, run `python -m pytest agents/tests/test_flash_sale_e2e.py -q`. The timeline uses the report's values, including W2's utility (0.69), 84 MB network transfer, 27 seconds, NAPFD 0.94, and human wait points.

## Guardrails in this prototype

- Every pipeline transition, approval, and irreversible-action attempt inserts an audit row. `audit_log` has a database trigger that rejects UPDATE and DELETE.
- The autonomy decision is `probability >= tau AND risk <= risk_max`. Escalations pause the state machine and enter its approval queue.
- Merge and full production deploy callbacks are never invoked unless `human_approved=True`; the existing SQL schema enforces the same invariant.
- Node runtimes accept signed Ed25519 bundles and return only allowlisted aggregate fields. Container CPU/memory limits and subprocess timeout bound the classroom sandbox.
- Node runtimes never receive the raw production log in the demo. Only the bundle's small synthetic state is used.
- The sandbox emits prototype outputs for all nine workflow stages. Investigation uses ticket-text heuristics, planning uses a template, implementation drafts a request only, QA lists checks without running CI, deployment proposes a canary without executing it, and monitoring has no telemetry source. These limits are visible in the output and history rather than presented as production actions.

This is intentionally a teaching scaffold, not a production isolation boundary: arbitrary Python bundle execution still shares the node container's kernel. Do not expose these demo containers to untrusted users or production networks.

## Optional OpenRouter triage

The manual ticket sandbox can call OpenRouter from Broker-Triage when `OPENROUTER_API_KEY` is set. It prioritizes `qwen/qwen3.8-27b:free` and falls back to `inclusionai/ling-3.0-flash-sante:free` on provider errors; configure `OPENROUTER_MODEL` and `OPENROUTER_FALLBACK_MODEL` to change that order. The defaults are in `docker-compose.yml` and `.env.example`. Configure the key in an untracked root `.env` file for Docker Compose, or leave it unset to use local rule-based triage. Masked ticket and reviewer text is sent to OpenRouter only when the key is configured. Requests time out and fall back to rules if both models fail. LLM severity proposals have confidence capped below the autonomy threshold, so they require human review. Merge and release checkpoints remain explicitly approval-gated.

At a review checkpoint, reviewers can accept, reject, or request changes. Accepted notes are interpreted as context for the next stage. A change request is interpreted into requested changes, constraints, and evidence, then sent to the responsible stage agent. Triage interprets the note and revises severity in one OpenRouter call. If OpenRouter is unavailable, a clear explicit severity correction is applied locally; other triage changes stay paused for clarification. QA adds requested checks to its draft. Deployment records constraints in its proposal but never deploys. Each note, interpretation, ACL handoff, revision output, and final decision is appended to the Postgres audit log and appears in Ticket history. Fallback reasons are recorded without exposing API credentials.
