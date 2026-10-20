# Evaluation harness

This package implements the four-arm experiment for the course prototype. Sections 9.1–9.5 of the report call for identical ticket sets across four arms, five seeds, paired Wilcoxon, Friedman with Nemenyi post-hoc, Cliff's delta, and Holm-Bonferroni correction. The default config runs seeds 42–46 with 100 synthetic tickets per seed, so each arm processes 500 tickets, and all four arms receive the same tickets.

## Run

From the repository root:

```sh
python -m pip install -r eval/requirements.txt
make eval
```

The command creates a new `results/<UTC timestamp>/` directory with a config snapshot, environment metadata, per-ticket and per-stage CSV files, security injection results, summary and statistics CSV files, BAB 9.4 Markdown, ROC data, and three PNG charts. Seeds, ticket count, `alpha`, `tau`, and `risk_max` are read from `eval/config.json`. With a single seed the run stays descriptive and `statistical_tests.csv` is not written, because the paired tests use one block per seed.

## Interpretation

- Each seed creates one ticket set; the exact same records are passed to A0–A3.
- Severity uses chronological 70/30 training/evaluation slices and TF-IDF + Platt-calibrated LinearSVC.
- Wall time, CPU time, and traced peak memory are measurements from the current Python host, and can vary between runs and machines despite fixed data seeds. The simulated lead time adds measured wall time, so it also varies slightly.
- ACL payload sizes use the serializer shared with `RedisStreamBus`; A3 migration size uses `MobileAgentRuntime`'s bundle serializer and a representative aggregate return. These are logical payload bytes, not transport framing or an actual network measurement.
- Token values are character-count estimates. No LLM endpoint, Redis, PostgreSQL, container runtime, or deployment service is called.
- The ticket generator, deployment outcomes, lead times, and DORA aggregates are synthetic. The policy injection suite is also synthetic and demonstrates that the implemented checks block the four injected categories; it is not a production security certification.
- Full deployment is guarded in the harness by `human_approved`; `full_deploy_without_approval` is emitted as a directly checkable invariant.

Result CSVs include `dataset_version`; chart metadata and report headers carry the same identifier.

## Statistical tests

`statistical_tests.csv` compares the per-seed means of wall time, network bytes, CPU seconds, and rollback. Results are exploratory because five seeds give only a small paired sample:

- With five seeds, the smallest possible two-sided Wilcoxon p-value is 0.0625. No pairwise test can reach `alpha = 0.05`, and Holm-Bonferroni correction across the 24 pairs raises every p-value to 1.0.
- With four arms and five seeds, the smallest Friedman p-value is 0.0018. It occurs when the arms keep the same order in every seed.
- The network-bytes and rollback tests are deterministic and repeat exactly. The wall-time and CPU tests depend on host timing and change between runs.

## Reproducing reported numbers

With the current code, `make eval` reproduces every non-timing column of [`results/20260930T020846305626/`](../results/20260930T020846305626/), the run that both the final report (§9.4–9.5) and the presentation deck cite. That covers bytes, messages, macro-F1, NAPFD, Recall@5, MAP, rollback, full-release counts, the security injections, and the bytes and rollback Friedman tests. That folder holds the original five-seed output of that run. Its plotting step stopped on the `boxplot(labels=)` keyword, so it has no charts or ROC file; the current `report.py` works on matplotlib 3.10 and 3.11+.

The report's wall times in Tabel 40 (0,102–0,198 ms) and its wall-time Friedman p = 0,0136 are that run's host observations; a rerun measures different values.

An earlier run, `results/20260929T145202896406Z`, was produced before the duplicate-retrieval fix and reported MAP above 1. It is no longer in the working tree but remains in git history: `git show da03470:results/20260929T145202896406Z/summary.csv`. Report versions before 2026-10-20 cited its timings.
