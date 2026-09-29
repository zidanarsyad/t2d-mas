# T2D-MAS agents prototype

This course prototype provides an auditable agent interface, Redis Streams ACL-style messaging, Contract Net worker selection, signed mobile bundles, node APIs, and a nine-stage pipeline.

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

Try `GET http://localhost:8000/health`, then `POST http://localhost:8000/demo/migrate/1` to send a signed demonstration bundle to node 1. Redis messaging is exposed through `POST /messages`, `GET /messages/next?consumer=worker-1`, and `POST /messages/{stream_id}/ack`; distinct consumer names allow parallel consumers. `GET /approvals` shows pending human decisions. `POST /tickets` creates an in-memory pipeline ticket; call `/tickets/{id}/approve` and then `/tickets/{id}/resume` to resolve a queued checkpoint. The orchestrator stores its private signing key in a volume unavailable to node containers; nodes mount only the public key.

For the reproducible §8.5 flash-sale timeline, run `python -m pytest agents/tests/test_flash_sale_e2e.py -q`. The timeline uses the report's values, including W2's utility (0.69), 84 MB network transfer, 27 seconds, NAPFD 0.94, and human wait points.

## Guardrails in this prototype

- Every pipeline transition, approval, and irreversible-action attempt inserts an audit row. `audit_log` has a database trigger that rejects UPDATE and DELETE.
- The autonomy decision is `probability >= tau AND risk <= risk_max`. Escalations pause the state machine and enter its approval queue.
- Merge and full production deploy callbacks are never invoked unless `human_approved=True`; the existing SQL schema enforces the same invariant.
- Node runtimes accept signed Ed25519 bundles and return only allowlisted aggregate fields. Container CPU/memory limits and subprocess timeout bound the classroom sandbox.
- Node runtimes never receive the raw production log in the demo. Only the bundle's small synthetic state is used.

This is intentionally a teaching scaffold, not a production isolation boundary: arbitrary Python bundle execution still shares the node container's kernel. Do not expose these demo containers to untrusted users or production networks.
