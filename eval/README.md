# Evaluation harness

This package implements the requested four-arm experiment for the course prototype. The attached report is treated as a domain and formatting reference: §9.4 asks for identical ticket sets across four arms, five seeds, paired Wilcoxon, Friedman with Nemenyi post-hoc, Cliff's delta, and Holm-Bonferroni correction. The harness request defines what is implemented; report text that labels values as targets is not treated as measured results.

## Run

From the repository root:

```sh
python -m pip install -r eval/requirements.txt
make eval
```

The command creates a new `results/<UTC timestamp>/` directory with a config snapshot, environment metadata, per-ticket and per-stage CSV files, security injection results, summary/statistics CSV files, BAB 9.4 Markdown, ROC data, and three PNG charts. Seed and ticket count can be adjusted in `eval/config.json`.

## Interpretation

- Each seed creates one ticket set; the exact same records are passed to A0–A3.
- Severity uses chronological 70/30 training/evaluation slices and TF-IDF + Platt-calibrated LinearSVC.
- Wall time, CPU time, and traced peak memory are measurements from the current Python host, and can vary between runs and machines despite fixed data seeds.
- ACL payload sizes use the serializer shared with `RedisStreamBus`; A3 migration size uses `MobileAgentRuntime`'s bundle serializer and a representative aggregate return. These are logical payload bytes, not transport framing or an actual network measurement.
- Token values are character-count estimates. No LLM endpoint, Redis, PostgreSQL, container runtime, or deployment service is called.
- The ticket generator, deployment outcomes, lead times, and DORA aggregates are synthetic. The policy injection suite is also synthetic and demonstrates that the implemented checks block the four injected categories; it is not a production security certification.
- Full deployment is guarded in the harness by `human_approved`; `full_deploy_without_approval` is emitted as a directly checkable invariant.

Result CSVs include `dataset_version`; chart metadata and report headers carry the same identifier. Statistical results are exploratory because five seeds provide only a small paired sample.
