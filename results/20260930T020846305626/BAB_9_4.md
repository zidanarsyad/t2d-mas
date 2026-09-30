# BAB 9.4 — Four-arm evaluation

Dataset version: `synthetic-eval-v1`; seeded synthetic ticket set; five fixed seeds; identical tickets are passed to all arms.
Wall-clock/CPU/memory values are observations on this host. LLM tokens are character-based estimates;
network bytes use the ACL/mobile bundle serializers but do not include transport framing. DORA values are simulated.
Severity ROC uses the chronological 30% holdout and a TF-IDF + Platt-calibrated LinearSVC.

| Arm | Approach | Tickets | Mean time (s) | P95 time (s) | Mean bytes | Messages | Token estimate | Macro-F1 | NAPFD | Rollback |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A0 | Rule-based, single process | 500 | 0.0001 | 0.0002 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.4900 | 0.0560 |
| A1 | Single agent | 500 | 0.0002 | 0.0003 | 1778.0000 | 6.0000 | 186.4920 | 1.0000 | 0.7500 | 0.0540 |
| A2 | Multi-agent with static agents | 500 | 0.0002 | 0.0004 | 3556.0000 | 12.0000 | 186.4920 | 1.0000 | 0.7500 | 0.0580 |
| A3 | Multi-agent with mobile agents | 500 | 0.0002 | 0.0003 | 4161.0000 | 13.0000 | 186.4920 | 1.0000 | 0.7500 | 0.0740 |

## DORA-style metrics

| Arm | Deployments/day | Mean lead time (h) | Recovery (h) | Change failure rate | Rework rate |
|---|---:|---:|---:|---:|---:|
| A0 | 2.9600 | 4.9642 | 1.1161 | 0.0560 | 0.1000 |
| A1 | 2.9467 | 4.9690 | 1.3056 | 0.0540 | 0.1000 |
| A2 | 2.9800 | 4.9716 | 1.1121 | 0.0580 | 0.1000 |
| A3 | 2.8867 | 4.9728 | 1.1081 | 0.0740 | 0.1000 |

Full per-ticket and per-stage measurements are in `per_ticket.csv` and `per_stage.csv`.
See `statistical_tests.csv` for paired Wilcoxon, Friedman/Nemenyi, Cliff’s delta, and Holm-adjusted results.
The synthetic policy-injection suite targets zero cases passed to the next stage.
