# BAB 9.4 — Four-arm evaluation

Dataset version: `synthetic-eval-v1`; fixed seed 42; identical tickets are passed to all arms.
Wall-clock/CPU/memory values are observations on this host. LLM tokens are character-based estimates;
network bytes use the ACL/mobile bundle serializers but do not include transport framing. DORA values are simulated.
Severity ROC uses the chronological 30% holdout and a TF-IDF + Platt-calibrated LinearSVC.

| Arm | Approach | Tickets | Mean time (s) | P95 time (s) | Mean bytes | Messages | Token estimate | Macro-F1 | NAPFD | Rollback |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A0 | Rule-based, single process | 100 | 0.0001 | 0.0002 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.4900 | 0.0700 |
| A1 | Single agent | 100 | 0.0002 | 0.0003 | 1778.0000 | 6.0000 | 186.4800 | 1.0000 | 0.7500 | 0.0300 |
| A2 | Multi-agent with static agents | 100 | 0.0002 | 0.0004 | 3556.0000 | 12.0000 | 186.4800 | 1.0000 | 0.7500 | 0.0400 |
| A3 | Multi-agent with mobile agents | 100 | 0.0002 | 0.0005 | 4161.0000 | 13.0000 | 186.4800 | 1.0000 | 0.7500 | 0.1000 |

## DORA-style metrics

| Arm | Deployments/day | Mean lead time (h) | Recovery (h) | Change failure rate | Rework rate |
|---|---:|---:|---:|---:|---:|
| A0 | 2.9000 | 4.9646 | 1.1071 | 0.0700 | 0.1000 |
| A1 | 3.0667 | 4.9713 | 1.3333 | 0.0300 | 0.1000 |
| A2 | 3.0667 | 4.9770 | 1.0000 | 0.0400 | 0.1000 |
| A3 | 2.8667 | 4.9761 | 1.2750 | 0.1000 | 0.1000 |

Full per-ticket and per-stage measurements are in `per_ticket.csv` and `per_stage.csv`.
Only seed 42 is used. Cross-seed consistency and statistical significance tests are not run.
The synthetic policy-injection suite targets zero cases passed to the next stage.
