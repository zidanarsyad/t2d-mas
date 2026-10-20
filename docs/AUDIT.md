# Audit: the prototype against the original idea

*Date: 20 October 2026.* This compares the code with two documents:
- the original idea: `docs/Project 1 - Idea.pdf`;
- the design in the final report: `docs/Laporan_Proyek1_T2D-MAS_Final.pdf`, §2–§8 and Lampiran B.

It records:
- what the code did before this cleanup;
- what it does now;
- what is still missing;
- where the report no longer matches the code.

## Summary

**Before the cleanup**, the live demo implemented only a thin slice of the idea:
- **What worked:** severity triage, the autonomy gate, the Contract Net formula and two fixed human checkpoints.
- **Canned stages:** every other stage returned fixed text.
- **Missing duplicate detection:** finding duplicates is one of the idea's four core problems, and it was not in the live pipeline.
- **Mobile agent outside the pipeline:** it only ran in a separate demo route, and the data nodes held no data of their own.
- **Unused code:**
  - the five-component agent base class was never used;
  - 10 of the 12 database tables were never written, so the merge and deploy guards never fired.
- **Dashboard:** it had overlapping views and no animation.

**Now**, every stage is carried out by an agent with the five components from the report:
- **Feedback capture:** it reads natural-language feedback in Indonesian and English and masks personal data.
- **Triage:** it checks for duplicates against earlier tickets before judging severity.
- **Assignment:** the Contract Net auction picks the squad that actually investigates.
- **Investigation:** a mobile agent visits six data nodes that keep their own logs.
- **Merge and release:** merging and releasing really happen in the system, and only after a named person approves.
- **Monitoring:** it can open a follow-up ticket, which closes the feedback loop.

Wherever the prototype has no real system to talk to (repository, CI, cluster, telemetry), a seeded, deterministic simulator stands in and the output says it is simulated.

## Stage by stage

| Stage (idea §2, report §2.1) | Idea / report | Before | Now |
|---|---|---|---|
| 1 Feedback capture | Portal, e-mail, Slack and crash-reporter channels. Normalize the version, device and steps. Mask PII (F-01, F-02). | Typed title and body; masking only | Scout-Feedback reads a message from six channels, detects the language, derives a title, extracts the version, device and reproduction hints, and guesses the product area. It reports how much PII it masked. Demo inbox: 42 realistic messages in Indonesian and English. |
| 2 Smart triage: duplicates | Cosine similarity: ≥ 0.85 auto-link, 0.70–0.85 human, otherwise new (§3.1, §6.4.1, T21) | Not in the live pipeline | TF-IDF cosine over character n-grams against earlier tickets, with the three bands. Auto-linked tickets close and point to the original; the middle band waits for a person. It reproduces the idea's worked example (0.994 / 0.119). |
| 2 Smart triage: severity + gate | Softmax probabilities; act alone only if P ≥ τ **and** risk ≤ R_max (§4.3, eq. 24) | English keyword rules plus optional OpenRouter; gate at triage | Same gate, plus Indonesian cue words and slang normalization. Thresholds come from one policy module and the `policies` table. |
| 2 Assignment | Contract Net, U = 0.5·skill + 0.3·(1−load) + 0.2·(1−cost) (eq. 13) | Correct formula, but the winner was ignored | Three squads bid using their skill for the product area and their current load. The winner investigates, and the SLA follows the severity. |
| 3 Investigation | Scout-Log (mobile) aggregates on the nodes; GNN ranks suspect services (§6.6, B.3) | Keyword guesses; no node data | Scout-Log visits all six nodes. The break-even rule L > (A + R)·3 decides, per node, whether code is shipped there. Only aggregates return. Suspects are ranked with the report's GraphSAGE-mean calculation over the call chain. |
| 4 Planning | Subtasks, Given/When/Then criteria, estimate (T15, T26) | Fixed template | Generated from the investigation: subtasks with estimates, three Given/When/Then criteria, and a sprint-capacity check. |
| 5 Implementation | Draft PR; secret scan with injection demo (T19, T36) | "No code generated" | A simulated draft PR is stored in `code_changes`. Security-Policy scans it, and a leaked secret blocks it until it is redrafted (demo switch `inject_test_secret`). |
| 6 QA | RL test prioritization, NAPFD (§6.5.1, B.2) | "Not run" | Risk-aware selection of about 120 of 3,400 tests within an 8-minute budget, scored with the real NAPFD function. Merging always needs a review. |
| 7 Deployment | 5% canary on its own only if risk ≤ 0.30; full deploy never alone; auto-rollback (T21, §6.5.2) | Proposal only | Computes a risk score. Runs the canary itself or asks a person. An SLO breach rolls back automatically. The full release runs only after sign-off and is recorded in `deployments`. |
| 8–9 Monitoring and feedback loop | Anomalies against SLO baselines open new tickets (F-12, T37) | "Awaiting telemetry" | Post-release metrics are compared with the SLO baselines. An anomaly opens a follow-up ticket (demo switch `simulate_regression`), and so do monitoring-view alerts. |

## Architecture and governance

| Topic | Idea / report | Before | Now |
|---|---|---|---|
| Five agent components (§5.3.1, B.5) | perceive, remember, reason, act, report | `base.py` defined them, but nothing used it | `stage_agent.py` is used by all nine agents; each output lists the five steps in plain words. |
| Families (T14) | Scout, Broker, Worker, Security | Names only | Code is grouped the same way: `scouts.py`, `brokers.py`, `workers.py`, `security_policy.py`. |
| Mobile agents (§5.4) | Signed code to the data; break-even rule | Demo route only; nodes held no data; rule unused | Real trips during investigation, with the rule applied per node. Raw logs (with fake customer e-mails) provably stay on the nodes. |
| Messaging (§5.6) | FIPA-ACL on Redis Streams | Worked; dead consumer-group routes | Dead routes removed; the stream is bounded. The unused `signature` field is kept because the evaluation's byte counts include it. |
| Blackboard (§7.1) | PostgreSQL holds tickets, evidence, risk, policy | 2 of 12 tables used | Six tables, all used: tickets, audit_log, code_changes, deployments, policies, slo_baselines. |
| Human gates (§5.5) | Three gates | Conditional triage gate, plus merge and release | Six gate types. Merge and release always need a person. Duplicate review, the autonomy gate, the secret scan and canary review stop only when their rule says so. |
| Rule 1: no merge or deploy without `human_approved` | | Guard code existed but never ran | Enforced in three places: the orchestrator, `execute_irreversible` (which checks the recorded approval) and the database triggers. |
| Rule 2: append-only audit | | Row trigger only | UPDATE, DELETE **and** TRUNCATE are blocked. Every output, gate, message, approval and blocked action is logged. |
| Rule 3: raw data stays on nodes | | Nodes had no data | Nodes keep their own logs; only allowlisted aggregates leave. A test proves it. |
| Rule 4: reproducible numbers | | 5-seed evaluation restored | Simulators are seeded from the ticket id. `python -m eval.compare_runs` checks that a fresh evaluation matches the cited run, and it does. |
| Free APIs only | | Enforced for OpenRouter | Unchanged: only `:free` models, no key needed; local mode needs no services at all. |

## Code removed or fixed

**Deleted, because nothing used them:**
- `agents/base.py`, replaced by `stage_agent.py`;
- `agents/workflow_agents.py`, whose canned stage outputs were replaced by real agents;
- `agents/flash_sale.py` and its test, since the dashboard owns the illustrative replay;
- `data/mock_api/`, replaced by the in-process simulators in `agents/tools.py`;
- seven API routes:
  - `POST /tickets`, `/tickets/{id}/approve`, `/tickets/{id}/resume`;
  - `GET /approvals`;
  - `POST /messages`, `/messages/next`, `/messages/{id}/ack`;
- the Redis consumer-group code;
- the unused `rca_top_k` and `mean_average_precision` in `eval/metrics.py`;
- six unused tables and the pgvector extension;
- 25 committed `.pyc` files and a PowerPoint lock file.

**Merged duplicates:**
- One autonomy-gate rule: `agents/security_policy.py` now delegates to `triage/gate.py`.
- One NAPFD: `envs/metrics.py` re-exports the one in `eval/metrics.py`.
- One PII masker: `data/preprocess.py` uses `agents/pii.py`.
- One stage list and one policy module, instead of literals repeated across files.

**Bugs fixed:**
- `data/preprocess.py` could leak part of an e-mail address, because version masking ran before e-mail masking.
- Dates were masked as phone numbers.
- The Contract Net winner was ignored.
- `app.py` (977 lines) is split into four small route modules and two services.

**Repository hygiene:**
- `.gitignore` and `.dockerignore` added. The Docker build context no longer includes the local `.venv` (PyTorch and friends).
- PostgreSQL is now published on localhost only.

## Evaluation findings (reported, not changed)

You chose to keep the evaluation exactly as the report cites it. These are worth stating as limitations:

1. **Label leakage.** `agents/synthetic_data.py` puts a severity phrase in every title ("critical data loss", "minor cosmetic", …).
   - Severity Macro-F1 is therefore 1.0 for every arm in every run.
   - All arms also share one set of predictions, so F1 cannot differ between arms.
   - Fixing this needs new evaluation tickets, and that would change every number in the report.
2. **Duplicate metrics use a stand-in.** Duplicate recall and MAP in the harness come from a word-overlap stand-in, not from the MiniLM/FAISS model in `triage/`.
3. **Timings vary by machine.** Wall time, CPU, memory and the lead time derived from them are host measurements; they vary between machines even with fixed seeds.

## Where the report no longer matches the code

These are for whoever edits the Google Doc behind the PDF. The PDF and PPTX were not edited.

- **Abstract and §5.5:** "three approval gates". Now six gate types: merge and release always; duplicate review, autonomy, secret scan and canary review only when their rule triggers.
- **§6.4:** live duplicate detection uses TF-IDF over character n-grams (the idea's "TF-IDF sederhana"). SBERT/FAISS stays in the offline `triage/` module.
- **§7.1, T28:** the schema has six tables (listed above); `ticket_embeddings`, `agents`, `messages`, `evidence`, `tasks` and `test_runs` were removed, and pgvector is not used.
- **§7.4, T32:** the mock enterprise APIs are now in-process simulators (`agents/tools.py`).
- **B.5:** the agent base class is `agents/stage_agent.py` (`StageAgent.run()` calls perceive, remember, reason, act and report).
- **T35, and §8.3 / B.6:** the dashboard views and styling changed.
  - The screen names changed.
  - Tailwind was removed.
  - See `frontend/README.md`.
- **Tabel 41:** the 20 security injections are reported (20 blocked, 0 passed).

## Still not built

- **No real systems.** No real repository, CI runner, deployment target or telemetry; seeded simulators stand in.
- **No live models.** The trained models stay offline in `triage/`, `rca/` and `envs/`: MiniLM + FAISS for duplicates, the trained GraphSAGE model, and the PPO/DQN policies. The live pipeline uses their simpler counterparts.
- **No undo window.** The report's 30-second undo for autonomous actions is not built.
- **No login.** Approvals record a name, not an authenticated identity.
- **Cross-language duplicates are missed.** Lexical similarity cannot match an Indonesian and an English report of the same problem.
- **Rules tuned in-sample.** The component guess and severity rules were tuned on the demo messages they are tested on.
