# BAB 9.4 — Four-arm evaluation

Dataset version: `synthetic-eval-v1`; fixed seeds 42, 43, 44, 45, 46; 100 tickets per seed, 500 per arm; identical tickets are passed to all arms.
Wall-clock/CPU/memory values are observations on this host. LLM tokens are character-based estimates;
network bytes use the ACL/mobile bundle serializers but do not include transport framing. DORA values are simulated.
Severity ROC uses the chronological 30% holdout and a TF-IDF + Platt-calibrated LinearSVC.

| Arm | Approach | Tickets | Mean time (ms) | P95 time (ms) | Mean bytes | Messages | Token estimate | Macro-F1 | NAPFD | Rollback |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A0 | Rule-based, single process | 500 | 0.084 | 0.117 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.4900 | 0.0560 |
| A1 | Single agent | 500 | 0.122 | 0.177 | 1778.0000 | 6.0000 | 186.4920 | 1.0000 | 0.7500 | 0.0540 |
| A2 | Multi-agent with static agents | 500 | 0.163 | 0.341 | 3556.0000 | 12.0000 | 186.4920 | 1.0000 | 0.7500 | 0.0580 |
| A3 | Multi-agent with mobile agents | 500 | 0.186 | 0.309 | 4161.0000 | 13.0000 | 186.4920 | 1.0000 | 0.7500 | 0.0740 |

## DORA-style metrics

| Arm | Deployments/day | Mean lead time (h) | Recovery (h) | Change failure rate | Rework rate |
|---|---:|---:|---:|---:|---:|
| A0 | 2.9600 | 4.9625 | 1.1161 | 0.0560 | 0.1000 |
| A1 | 2.9467 | 4.9660 | 1.3056 | 0.0540 | 0.1000 |
| A2 | 2.9800 | 4.9698 | 1.1121 | 0.0580 | 0.1000 |
| A3 | 2.8867 | 4.9718 | 1.1081 | 0.0740 | 0.1000 |

## Statistical tests (one paired block per seed, alpha = 0.05)

| Metric | Friedman chi-square | Friedman p | Wilcoxon pairs significant after Holm |
|---|---:|---:|---:|
| total_wall_time_s | 15.0000 | 0.0018 | 0 of 6 |
| network_bytes | 15.0000 | 0.0018 | 0 of 6 |
| cpu_seconds | 5.4375 | 0.1424 | 0 of 6 |
| rollback | 1.8511 | 0.6039 | 0 of 6 |

Full per-ticket and per-stage measurements are in `per_ticket.csv` and `per_stage.csv`.
See `statistical_tests.csv` for paired Wilcoxon, Friedman/Nemenyi, Cliff's delta, and Holm-adjusted results.
The synthetic policy-injection suite targets zero cases passed to the next stage.
