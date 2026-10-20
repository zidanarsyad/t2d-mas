# T2D-MAS data package

Ticket loaders, preprocessing and dataset statistics for the offline experiments, plus the PostgreSQL schema the live agents use as their shared blackboard (`schema.sql`).

## Setup

Use Python 3.11. Install the package dependencies and create a PostgreSQL database:

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

Preprocessing sorts by creation time and assigns consecutive 70/10/20 partitions (rounding goes to the test split). This chronological split prevents future-to-past leakage; it is not stratified by severity, so severity counts in each split are emitted by the statistics report instead. Text cleanup collapses consecutive repeated lines, masks e-mails, phone numbers and tokens first (using the same rules as the live agents in `agents/pii.py`), and then replaces version/build strings. Description lengths are measured in characters.

Each loader row, processed row, report row, and chart metadata carries or identifies `dataset_version`. By default loaders derive a content hash from normalized rows; give `--dataset-version` to keep one explicit label across multiple exports and splits.

## Database schema

`schema.sql` keeps only what the live system writes or reads:

| Table | Used for |
|---|---|
| `tickets` | Every ticket: loaded datasets, and tickets created from the dashboard |
| `audit_log` | Every agent action; triggers reject UPDATE, DELETE and TRUNCATE |
| `code_changes` | Draft pull requests; a trigger refuses `merged` without `human_approved` |
| `deployments` | Canary and production releases; a trigger refuses `deployed` without `human_approved` |
| `policies` | Autonomy thresholds and rules, seeded from `agents/policy.py` |
| `slo_baselines` | What "healthy" means per service, seeded from `agents/tools.py` |

The earlier mock enterprise API (`data/mock_api`) was removed: nothing used it. The agents now call seeded, in-process simulated tools (`agents/tools.py`), which play the same role (observability, project board, repository, CI and deploy) and are clearly labelled as simulated in every output.
