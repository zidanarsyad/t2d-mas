# T2D-MAS data package

This is a small course-project implementation. The supplied report names the tables in §7.1 but refers to an ERD image that is not included. §7.4 describes mock integrations and gives one ticket example; it does not include an API contract table. The schema and mock routes therefore use the requested table list and the report's ticket fields as the compact working contract.

## Setup

Use Python 3.11. Install the package dependencies and create a PostgreSQL database with the `vector` extension available:

```powershell
python -m pip install -r data/requirements.txt
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/t2dmas"
psql $env:DATABASE_URL -f data/schema.sql
```

Set `DATABASE_URL` only when loading into PostgreSQL; omitting it writes Parquet only. Loader output is upserted by `ticket_id`, and its Parquet file is replaced on rerun.

## Load tickets

GitBugs accepts local CSV/JSON/JSONL/Parquet exports or a direct download URL:

```powershell
python -m data.loaders.gitbugs --input data/input/gitbugs.csv --parquet data/output/gitbugs.parquet
python -m data.loaders.gitbugs --url https://example.org/issues.csv --dataset-version gitbugs-2026-09
```

The Eclipse/Mozilla loader accepts a local export, direct JSON URL, or pages through the public Bugzilla API. The default is Mozilla and the default cap is 5,000 records for a class-sized run.

```powershell
python -m data.loaders.eclipse_mozilla --host eclipse --max-records 1000 --parquet data/output/eclipse.parquet
python -m data.loaders.eclipse_mozilla --input data/input/bugs.json --host mozilla
```

The stable row fields are `ticket_id`, `title`, `body`, `component`, `severity`, `created_at`, and `duplicate_of`; `source`, `dataset_version`, and `pii_masked` are metadata columns. Public Bugzilla documentation describes its REST API at `/rest/bug`; GitBugs provides CSV issue exports.

## Preprocess and report

```powershell
python -m data.preprocess --input data/output/gitbugs.parquet --output-dir data/output/processed
python -m data.report_dataset_stats --input data/output/processed/train.parquet --output-dir data/output/stats
```

Preprocessing sorts by creation time and assigns consecutive 70/10/20 partitions. This chronological split prevents future-to-past leakage; severity counts in each split are emitted by the statistics report instead of forcing a stratified shuffle. Text cleanup collapses consecutive repeated lines, replaces version/build strings, and masks email, phone, and common token patterns. Description lengths are measured in characters.

Each loader row, processed row, report row, mock API response, and chart metadata carries or identifies `dataset_version`. By default loaders derive a content hash from normalized rows; give `--dataset-version` to keep one explicit label across multiple exports and splits.

## Mock enterprise APIs

```powershell
uvicorn data.mock_api.app:app --reload
```

Routes cover `/jira/tickets`, `/github/pulls`, `/observability/metrics/{service}`, `/ci/runs`, `/infra/deployments`, and read-only `/audit-log`. Each request gets 50–300 ms latency and a 2% simulated 503 rate by default. `MOCK_SEED` controls the deterministic random sequence. Merge and deployment routes always require `human_approved=true`; confidence/risk gate inputs are captured in audit details and failed gates are escalated. The API returns aggregate observability features rather than raw logs. In-memory mock state resets when the process restarts; durable project records belong in PostgreSQL.

The SQL schema rejects UPDATE/DELETE on `audit_log` and guards merge/deploy rows so they cannot be marked successful without human approval.
