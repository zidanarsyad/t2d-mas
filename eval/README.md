# Evaluation harness

This package compares four approaches using only seed 42, as requested by the user. The supplied report remains a domain and formatting reference; its multi-seed statistical design is not executed. All four arms receive the same 100 synthetic tickets.

## Run

From the repository root:

```sh
python -m pip install -r eval/requirements.txt
make eval
```

The command creates a new `results/<UTC timestamp>/` directory with a config snapshot, environment metadata, per-ticket and per-stage CSV files, security injection results, summary CSV files, BAB 9.4 Markdown, ROC data, and three PNG charts. Ticket count can be adjusted in `eval/config.json`; the runner requires `seeds: [42]` and `master_seed: 42`.

## Interpretation

- Seed 42 creates one ticket set; the exact same records are passed to A0–A3.
- Severity uses chronological 70/30 training/evaluation slices and TF-IDF + Platt-calibrated LinearSVC.
- Wall time, CPU time, and traced peak memory are measurements from the current Python host, and can vary between runs and machines despite the fixed data seed.
- ACL payload sizes use the serializer shared with `RedisStreamBus`; A3 migration size uses `MobileAgentRuntime`'s bundle serializer and a representative aggregate return. These are logical payload bytes, not transport framing or an actual network measurement.
- Token values are character-count estimates. No LLM endpoint, Redis, PostgreSQL, container runtime, or deployment service is called.
- The ticket generator, deployment outcomes, lead times, and DORA aggregates are synthetic. The policy injection suite is also synthetic and demonstrates that the implemented checks block the four injected categories; it is not a production security certification.
- Full deployment is guarded in the harness by `human_approved`; `full_deploy_without_approval` is emitted as a directly checkable invariant.

Result CSVs include `dataset_version`; chart metadata and report headers carry the same identifier. Results are descriptive for one fixed seed. Cross-seed consistency and statistical significance checks are not run. The saved result bundles retain the original seed-42 measurements; their summaries and charts were rebuilt after removing other seeds.
