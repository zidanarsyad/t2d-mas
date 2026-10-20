# T2D-MAS Process and Experiments

This document describes the implemented course prototype from ticket intake through evaluation. It distinguishes executable behavior from synthetic demonstrations so that measured output is not confused with a production claim.

## 1. Project objective and guardrails

T2D-MAS explores a ticket-to-deployment pipeline coordinated by software agents. The flow covers feedback capture (intake), triage, assignment, investigation, planning, implementation, QA, deployment, and monitoring, with a feedback loop from monitoring back to triage. In the interactive prototype every stage is run by an agent; where no real system exists (repository, CI runner, cluster, telemetry) the agent calls a seeded simulator and labels its output as simulated. It never modifies a real repository or deploys to production. [AUDIT.md](AUDIT.md) compares each stage with the original idea.

The project keeps four system rules visible throughout that flow:

1. **Human approval is required for irreversible actions.** Merge and full-deployment callbacks are blocked without `human_approved=True`.
2. **Agent decisions are auditable.** Agent outputs, gate decisions, messages, approvals and blocked actions are appended to `audit_log`; the PostgreSQL schema rejects UPDATE, DELETE and TRUNCATE on it.
3. **Raw data stays on the nodes.** Each data node keeps its own (simulated) service logs; the Scout-Log agent runs signed code next to them or asks the node's exporter, and only allowlisted aggregate fields come back.
4. **Experiments are seeded.** Synthetic inputs and algorithmic choices are controlled by fixed seeds (seeds 42–46 for the four-arm harness, seed 42 for the RL commands) and written with dataset-version metadata. Timings and resource measurements are host observations and can vary between runs.

The autonomy gate is:

```text
allow autonomously iff confidence >= tau AND risk <= risk_max
otherwise pause the pipeline and request human review
```

The default policy uses `tau = 0.70` and `risk_max = 0.60`. Risk values are Low `0.1`, Medium `0.3`, High `0.6`, and Critical `1.0`; a high-confidence Critical classification still escalates because its risk exceeds the maximum.

## 2. End-to-end ticket process

### 2.1 Ticket data and preprocessing

The `data/` package supports local CSV, JSON, JSONL, and Parquet exports, plus explicit public-source downloads. The GitBugs and Eclipse/Mozilla loaders map source-specific records to a shared ticket schema:

```text
ticket_id, title, body, component, severity, created_at, duplicate_of
```

The loaders can write Parquet and optionally upsert tickets into PostgreSQL. Dataset versions are derived from normalized content unless a version is supplied.

Preprocessing then:

- collapses consecutive repeated stack-trace lines while retaining a count marker;
- normalizes version/build strings;
- masks common email, phone, and token patterns;
- sorts by timestamp and ticket ID;
- splits chronologically into 70% train, 10% validation, and 20% test.

The chronological split avoids training on later tickets and evaluating on earlier ones. Missing or invalid timestamps are excluded from these time-based splits. A dataset manifest records the version and row counts.

### 2.2 Triage: duplicate detection and severity

The `triage/` package has four pieces:

- **Embeddings:** a lazy Sentence Transformers wrapper defaults to `all-MiniLM-L6-v2` and L2-normalizes vectors. Model inference is local. Public model downloads are opt-in; the TF-IDF baseline requires no model download.
- **Duplicate search:** `DuplicateDetector` stores normalized vectors in FAISS `IndexFlatIP`, so inner product is cosine similarity. The routing bands are auto-link at or above `tau` (default `0.85`), human review from `0.70` to below `tau`, and a new ticket below `0.70`.
- **Severity:** the baseline is TF-IDF plus `LinearSVC`, calibrated with Platt sigmoid calibration. An optional DistilBERT fine-tuning path uses Hugging Face Trainer and returns softmax probabilities.
- **Gate:** predicted class confidence and risk are combined using the autonomy rule above. The decision contains the selected class, confidence, risk, thresholds, and whether to proceed or escalate.

The separate `triage/` package does not require API keys and is run offline. The live Broker-Triage agent uses a lighter version of the same two steps: duplicate search with TF-IDF over character 3–5-grams and cosine similarity (same bands), and local severity rules in English and Indonesian, with optional OpenRouter proposals (free models only) when a key is configured. Those proposals remain below the autonomy confidence threshold and require review. See [`triage/README.md`](../triage/README.md) for local model cache and optional download behavior.

### 2.3 Agent roles and collaboration

Every live agent runs the five-step cycle `perceive()`, `remember()`, `reason()`, `act()`, `report()` defined in [`agents/stage_agent.py`](../agents/stage_agent.py); its output lists the five steps in plain words, and the pipeline writes it to the audit log. The four archetypes are grouped in code as in the report (`scouts.py`, `brokers.py`, `workers.py`, `security_policy.py`):

| Archetype | Main responsibility in the pipeline |
|---|---|
| Scout | Gather ticket context, telemetry summaries, and post-deployment observations |
| Broker | Deduplicate/triage tickets and coordinate assignment |
| Worker | Investigate, plan, implement, and run tests |
| Security | Check policy, secrets, signatures, egress fields, and approval requirements |

The Redis Streams bus carries FIPA-ACL-style messages with performative, correlation ID, content and policy context (a `signature` field is reserved and left empty; only mobile bundles are signed). The stream is the shared, bounded conversation log that the dashboard replays. Contract Net assignment sends a call for proposals to three investigation squads, gathers bids until a deadline, then awards the ticket to the highest utility; the winner really investigates it:

```text
U = 0.5 * skill + 0.3 * (1 - load) + 0.2 * (1 - cost)
```

### 2.4 Nine-stage orchestration and human checkpoints

The orchestrator advances one ticket at a time through these stages:

1. Intake
2. Triage
3. Assignment
4. Investigation
5. Planning
6. Implementation
7. QA
8. Deployment
9. Monitoring

Six gates can pause a ticket. Two always do: pull-request review after QA (`pr_merge`) and release sign-off at deployment (`release_signoff`); the orchestrator adds these itself even if an agent forgot to ask. Four pause only when their rule triggers: `duplicate_review` (similarity 0.70–0.85), `autonomy_gate` (confidence below `tau` or risk above `risk_max`, so every Critical prediction), `secret_scan` (a secret in the draft change; it can only be redrafted or stopped) and `canary_review` (release risk score above 0.30). A pause creates an approval-queue entry; the reviewer can approve, request changes or reject, always with a reason. Rejection stops the run for good. Approval applies to the current stage only.

Merge and full deployment run through `execute_irreversible()`, which looks up the recorded approval for that gate, writes an audit record and only then performs the action; the `code_changes` and `deployments` tables refuse the same writes without `human_approved` (and so does the in-memory store used in local mode).

### 2.5 Static and mobile execution

Static agents process data where they run. During investigation, the Scout-Log mobile agent visits all six data nodes. For each node it applies the report's rule `L_node > (A + R) * 3` (`L_node` the node's log volume, `A` = 12 MB agent bundle, `R` = 2 MB result): above the 42 MB threshold it packages its analysis code into a signed Ed25519 bundle that the node verifies and runs next to its own logs; below it, it asks the node's built-in exporter. Either way only allowlisted aggregate fields return, and the investigator ranks the services on the call chain with the report's GraphSAGE-mean calculation.

The Compose demo provides one orchestrator, six node containers, Redis, and PostgreSQL; without Docker the same nodes run in-process (local mode). This demonstrates transport, signing, auditing, and aggregate egress. It is not a hardened isolation boundary for arbitrary untrusted code.

### 2.6 CI, canary release, and dashboard

The `envs/` package provides two seeded Gymnasium environments:

- **Test prioritization:** each test exposes normalized duration, cycles since last execution, historical failure ratio, flakiness, and diff proximity. The action is a continuous priority score per test. Tests are ordered under a time budget. Reward is `NAPFD - lambda_time * execution_seconds`.
- **Canary deployment:** state contains risk, diff size, QA pass ratio, hour, and rollback count. Actions are `hold`, `canary_5`, `canary_25`, and `full`. Hold costs `-0.2` per simulated hour; deployment gives `+1` without an SLO violation or `-5` on rollback. A full action is downgraded to hold unless a one-use human approval was supplied.

PPO is trained for test prioritization and canary choices; DQN is trained for the discrete canary environment. Offline canary training explicitly supplies simulated approval so algorithms can explore full rollout. The regular environment does not infer approval from an agent action.

The React dashboard shows the live pipeline with animations (the ticket moving through the stages, agent messages, the mobile agent's trip, monitoring and the feedback loop) and a replay mode that works without the backend; see [`frontend/README.md`](../frontend/README.md) for its views.

## 3. Experiment designs

### 3.1 Dataset and preprocessing checks

The data package is exercised with local or public ticket exports. The key checks are consistent field normalization, duplicate-preserving upserts, stable dataset-version metadata, deterministic PII masking, and chronological splitting. The public data path depends on the source being available; synthetic data is used when a repeatable test set is preferred.

### 3.2 Triage numerical fixtures

The triage unit fixtures verify report-level numbers independently of model training:

- cosine similarity for the supplied ticket vectors is approximately `0.994` for A/B and `0.119` for A/C;
- softmax of logits `[1.2, 0.5, 2.1, 0.3]` produces `P(High) ~= 0.564`;
- deduplication thresholds route scores at `0.85`, `0.70`, and below `0.70` to the expected zones;
- the gate allows or escalates based on both confidence and risk.

The fine-tuned transformer path is optional and separate from these deterministic numerical fixtures.

### 3.3 RCA experiment

The `rca/` package standardizes five service metrics—latency, error rate, CPU, memory, and saturation—against a per-service rolling seven-day baseline. Each trace call becomes a directed caller-to-callee edge weighted by request volume. The graph retains the directed edges and adds a bidirectional message-passing view so anomaly context can flow to callers and callees.

The model uses two request-volume-weighted GraphSAGE layers and a per-node suspiciousness readout. Training uses pairwise margin-ranking loss to put labeled incident nodes above non-incident nodes. GNNExplainer returns a compact explanation for the top suspicious nodes. A weighted PageRank implementation is the dependency-graph baseline.

The evaluation reports Top-1, Top-3, and mean reciprocal rank (MRR). The synthetic incident generator injects an anomaly into a known service node with a fixed seed. A numeric fixture separately checks the A→B→C weighted readout values `1.850`, `2.225`, and `2.600`; those fixed fixture scores are not a guarantee that learned model training produces the same values.

### 3.4 Reinforcement-learning experiment

The CI simulator generates 200 cycles with 20 tests by default. Durations, flaky tests, test history, and injected faults are generated from a fixed seed. If a public CI CSV is supplied, the loader expects `cycle_id`, `test_id`, `duration`, and `failed` and derives unavailable features conservatively.

Training reserves the first 80% of cycles for learning and the last 20% for evaluation. The CI policies compare PPO with random order and `failed_newest_first`. The canary policies compare PPO and DQN with random-action and risk-aware heuristic baselines. Evaluation writes NAPFD, time-to-first-failure when a failure was observed, and rollback ratio. These are offline environment outcomes, not live CI or production deployment results.

### 3.5 Four-arm harness

The `eval/` harness is the main comparative experiment. Default configuration is in [`eval/config.json`](../eval/config.json): five seeds `42`–`46`, 100 tickets per seed (500 per arm), `alpha=0.05`, `tau=0.70`, and `risk_max=0.60`. Each seed creates one ticket set; every arm receives exactly those same records. The runner reads `tau` and `risk_max` from this file for both the autonomy gate and the ACL policy context, and every result folder keeps a copy of the config it ran with.

The four arms are:

| Arm | Harness behavior |
|---|---|
| A0 | Rule-based, single-process behavior; original ticket order for prioritization and title-token similarity for duplicate retrieval |
| A1 | Single-agent behavior; severity-risk ordering and full-text similarity retrieval |
| A2 | Static MAS behavior; severity-risk ordering, full-text retrieval, and a small same-component score bonus |
| A3 | Mobile MAS behavior; same retrieval proxy as A2, plus a serialized mobile bundle and aggregate return in the investigation stage |

The severity model is TF-IDF plus Platt-calibrated LinearSVC. It is fit on the chronological first 70% and scored on the remaining 30%. This harness split differs intentionally from the data package's 70/10/20 train/validation/test split: the small harness currently has a train and evaluation split and does not use a separate validation partition.

For each ticket and each of six stages (triage, assignment, investigation, implementation, QA, deployment), the runner records:

- wall-clock seconds using `perf_counter`;
- CPU seconds using `process_time`;
- peak traced Python memory using `tracemalloc`;
- serialized ACL payload bytes and message count;
- an estimated token count based on text length divided by four.

The experiment is deliberately lightweight. It does not run live LLM calls, Redis, a PostgreSQL server, node containers, or actual deployment. ACL byte counts use the bus serializer; mobile byte counts use the bundle serializer plus a representative aggregate response. They exclude transport framing. Stage time measures a small deterministic workload plus instrumentation overhead, not end-to-end service latency. Token counts are estimates rather than billing records.

#### Metrics

The harness implements and emits:

- **Recall@k and MAP:** evaluated over tickets with a known `duplicate_of` target. The retrieval ranking uses visible title/body tokens and component metadata; it does not insert the target ID into the ranking. Duplicate examples are near-copy synthetic reports, so high retrieval scores should not be generalized to real ticket data.
- **Macro-F1:** average per-class F1 for Low, Medium, High, and Critical on the held-out severity rows.
- **NAPFD:** calculated from fault ranks in each arm's deterministic priority order.
- **DORA-style metrics:** deployment frequency per day in the simulated 30-day window, mean simulated lead time, mean recovery time for simulated failed deployments, change failure rate, and synthetic rework rate.
- **Security injections:** 20 synthetic cases—five each for secret-in-diff, deploy-during-freeze, PII-on-egress, and Critical severity without approval. The target is zero cases passed to the next stage.

#### Statistical tests

With more than one seed, the runner also writes `statistical_tests.csv`. Each seed is one paired block. For wall time, network bytes, CPU seconds, and rollback, the per-seed arm means are compared with:

- pairwise Wilcoxon signed-rank tests with Cliff's delta, Holm-Bonferroni corrected across the 24 pairs;
- a Friedman omnibus test with Nemenyi post-hoc pairs.

Five seeds give little statistical power. The smallest possible two-sided Wilcoxon p-value is 0.0625, so no pairwise test can reach `alpha = 0.05`. With four arms, the smallest Friedman p-value is 0.0018, which occurs when the arms keep the same order in all five seeds. Tests on network bytes and rollback are deterministic. Tests on wall time and CPU seconds inherit host timing noise and can change between runs. These results do not establish statistical superiority of any approach.

### 3.6 Re-running the experiments

From the repository root, install only the relevant dependencies. For the four-arm run:

```sh
python -m pip install -r eval/requirements.txt
make eval
```

When GNU Make is unavailable, use the same runner directly:

```sh
python -m eval.runner --config eval/config.json --output-root results
```

The command writes a new `results/<UTC timestamp>/` directory with a config snapshot, environment metadata, per-ticket and per-stage CSVs, security-injection detail and summary, descriptive summaries, statistical tests, BAB 9.4 Markdown, severity ROC data, and three charts. To train/evaluate the RL models, run the commands in [`envs/README.md`](../envs/README.md). To start the multi-container demo, use `docker compose up --build` and follow [`agents/README.md`](../agents/README.md).

## 4. Example harness output

The checked-in run at [`results/20260930T020846305626/`](../results/20260930T020846305626/) is the run that both the final report and the presentation deck cite. It used dataset version `synthetic-eval-v1`, seeds 42–46, and 500 ticket rows per arm. Rerunning `make eval` with the current code reproduces every column of its CSV files except four host-dependent ones: wall time, CPU time, traced memory, and the simulated lead time, which adds measured wall time. Selected results:

| Arm | Mean network bytes/ticket | Messages/ticket | Recall@5 | MAP | Macro-F1 | Mean NAPFD | Rollback rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| A0 | 0 | 0 | 0.429 | 0.242 | 1.000 | 0.490 | 0.056 |
| A1 | 1,778 | 6 | 1.000 | 0.680 | 1.000 | 0.750 | 0.054 |
| A2 | 3,556 | 12 | 1.000 | 0.687 | 1.000 | 0.750 | 0.058 |
| A3 | 4,161 | 13 | 1.000 | 0.685 | 1.000 | 0.750 | 0.074 |

Friedman omnibus tests over the five seeds:

| Metric | Friedman p | Repeats on a rerun? |
|---|---:|---|
| Network bytes | 0.0018 | Yes; deterministic |
| Rollback | 0.604 | Yes; deterministic |
| Wall time | 0.0136 | No; host timing |
| CPU seconds | 0.926 | No; host timing |

The injection summary recorded `20 blocked`, `0 passed`, meeting the synthetic target. A3 executed 11 simulated full releases, all of them human-approved; no arm executed a full release without approval. All four arms reached macro-F1 of 1.0 because the generated severity text contains highly distinctive class phrases; this is a generator sanity check, not evidence of equivalent real-world classifier accuracy. A3 records more bytes than A2 because this harness includes a mobile bundle and aggregate return in addition to ACL messages. Timings are tiny local workload measurements and should not be interpreted as an operational latency comparison.

That run's plotting step stopped on the `boxplot(labels=)` keyword, which newer matplotlib removed, so the folder has no charts or ROC file. `eval/report.py` now works on matplotlib 3.10 and 3.11+, and a fresh `make eval` writes all three charts.

See the [BAB 9.4 report](../results/20260930T020846305626/BAB_9_4.md), [statistical tests](../results/20260930T020846305626/statistical_tests.csv), [per-ticket data](../results/20260930T020846305626/per_ticket.csv), [per-stage data](../results/20260930T020846305626/per_stage.csv), and [security injection results](../results/20260930T020846305626/security_injection_summary.csv).

## 5. How to interpret and extend the results

The sample output verifies that the code paths run, the fixed seeds produce the intended synthetic inputs, and the stated policy checks block the included injection cases. It does **not** establish that a multi-agent architecture is faster, cheaper, safer, or more accurate on real enterprise tickets. In particular:

- synthetic severity phrases make the classification task unusually easy;
- duplicate reports are generated as near-copies and the harness retrieval proxy is lexical rather than the learned embedding/FAISS path;
- resource counts are simplified proxies; network bytes are serialized payload sizes, token counts are estimates, and deployment/DORA records are simulated;
- security injections cover four known patterns and do not constitute a broad adversarial security evaluation;
- the fixed seeds reproduce generated data and deterministic algorithmic decisions, but host timing and memory observations, the simulated lead time, and the wall-time and CPU tests can vary;
- five seeds give low statistical power, so the paired tests support discussion rather than claims of superiority.

For a stronger course experiment, replace the synthetic tickets with a versioned public/local export, preserve chronological train/validation/test boundaries, measure the same cases through the actual agent interfaces, log real message and mobile-runtime counters, and predefine an incident/deployment outcome record before calculating DORA-style metrics. Keep all raw production data on its source node and export only approved aggregate features.
