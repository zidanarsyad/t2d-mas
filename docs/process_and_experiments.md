# T2D-MAS Process and Experiments

This document describes the implemented course prototype from ticket intake through evaluation. It distinguishes executable behavior from synthetic demonstrations so that measured output is not confused with a production claim.

## 1. Project objective and guardrails

T2D-MAS explores a ticket-to-development pipeline coordinated by software agents. The intended flow covers intake, triage, assignment, investigation, planning, implementation, QA, deployment, and monitoring. The interactive prototype records heuristic results, drafts, human reviews, and simulated release/monitoring outputs; it does not modify a repository, execute CI, or deploy to production.

The project keeps four system rules visible throughout that flow:

1. **Human approval is required for irreversible actions.** Merge and full-deployment callbacks are blocked without `human_approved=True`.
2. **Agent decisions are auditable.** Actions, escalations, and approval decisions are appended to `audit_log`; the PostgreSQL schema rejects audit-row updates and deletes.
3. **Mobile-demo inputs stay local.** The signed node demo uses synthetic inputs and returns only allowlisted aggregate fields; production telemetry is not connected.
4. **Experiments are seeded.** Synthetic inputs and algorithmic choices are controlled by seed 42 and written with dataset-version metadata. Timings and resource measurements are host observations and can vary between runs.

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

The separate `triage/` package does not require API keys. Interactive Broker-Triage uses local rules by default, with optional OpenRouter proposals when a key is configured. Those proposals remain below the autonomy confidence threshold and require review. See [`triage/README.md`](../triage/README.md) for local model cache and optional download behavior.

### 2.3 Agent roles and collaboration

Agents share the abstract lifecycle `perceive()`, `remember()`, `reason()`, `act()`, and `report()`. Each agent records its action through an audit sink. The four project archetypes have these intended responsibilities:

| Archetype | Main responsibility in the pipeline |
|---|---|
| Scout | Gather ticket context, telemetry summaries, and post-deployment observations |
| Broker | Deduplicate/triage tickets and coordinate assignment |
| Worker | Investigate, plan, implement, and run tests |
| Security | Check policy, secrets, signatures, egress fields, and approval requirements |

The Redis Streams bus transports FIPA-ACL-style messages with performative, correlation ID, content, policy context, and signature fields. Consumer groups allow multiple workers to read messages in parallel. Contract Net assignment sends a call for proposals, gathers bids until a deadline, then accepts the highest utility:

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

There are three blocking checkpoints: severity sign-off at triage, pull-request review/merge after QA, and release sign-off at deployment. An escalated gate creates an approval-queue entry and the ticket cannot advance until a person approves it. Rejection stops the run; it cannot be resumed. Start a new run to reconsider the issue. Approval applies to the next transition; it is not a blanket authorization for later irreversible actions.

Merge and full-deployment callbacks are separately protected by `perform_irreversible()`, which checks the explicit human approval flag again and writes an audit record before execution.

### 2.5 Static and mobile execution

Static agents process data where they run. A mobile agent instead packages code and small state into a signed Ed25519 bundle and sends it to a node runtime. The runtime verifies the signature, executes the demonstration code inside a limited container, and returns only allowlisted aggregate results. The example migration rule is `L_node > (A + R) * 3`, where `L_node` is local data/log volume, `A` is agent bundle size, and `R` is expected return volume.

The Compose demo provides one orchestrator, six node containers, Redis, and PostgreSQL. This demonstrates transport, signing, auditing, and aggregate egress. It is not a hardened isolation boundary for arbitrary untrusted code.

### 2.6 CI, canary release, and dashboard

The `envs/` package provides two seeded Gymnasium environments:

- **Test prioritization:** each test exposes normalized duration, cycles since last execution, historical failure ratio, flakiness, and diff proximity. The action is a continuous priority score per test. Tests are ordered under a time budget. Reward is `NAPFD - lambda_time * execution_seconds`.
- **Canary deployment:** state contains risk, diff size, QA pass ratio, hour, and rollback count. Actions are `hold`, `canary_5`, `canary_25`, and `full`. Hold costs `-0.2` per simulated hour; deployment gives `+1` without an SLO violation or `-5` on rollback. A full action is downgraded to hold unless a one-use human approval was supplied.

PPO is trained for test prioritization and canary choices; DQN is trained for the discrete canary environment. Offline canary training explicitly supplies simulated approval so algorithms can explore full rollout. The regular environment does not infer approval from an agent action.

The React dashboard has nine views: Ticket overview, Agent conversations, Run a ticket, Human reviews, Decision trail, Ticket history, Meet the agents, Performance example, and Experiment results. Current runs share backend snapshots and recover messages from Redis history and server-sent events. Performance and conversation examples are explicitly labeled; experiment results read saved benchmark files. Agent roles describe configured responsibilities rather than fabricated live host health.

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

The `eval/` harness is the main comparative experiment. Default configuration is in [`eval/config.json`](../eval/config.json): only seed `42`, 100 tickets per arm, `tau=0.70`, and `risk_max=0.60`. Seed 42 creates one ticket set; every arm receives exactly those same records.

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
- **RCA Top-k:** general utility function, also used in the separate RCA experiment.
- **DORA-style metrics:** deployment frequency per day in the simulated 30-day window, mean simulated lead time, mean recovery time for simulated failed deployments, change failure rate, and synthetic rework rate.
- **Security injections:** 20 synthetic cases—five each for secret-in-diff, deploy-during-freeze, PII-on-egress, and Critical severity without approval. The target is zero cases passed to the next stage.

The runner writes descriptive summaries for seed 42 only. Cross-seed consistency, paired significance tests, and effect-size comparisons are not run. These results do not establish statistical superiority of any approach.

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

The command writes a new `results/<UTC timestamp>/` directory with a config snapshot, environment metadata, per-ticket and per-stage CSVs, security-injection detail and summary, descriptive summaries, BAB 9.4 Markdown, severity ROC data, and three charts. To train/evaluate the RL models, run the commands in [`envs/README.md`](../envs/README.md). To start the multi-container demo, use `docker compose up --build` and follow [`agents/README.md`](../agents/README.md).

## 4. Example harness output

The checked-in sample run at [`results/20260930T020846305626/`](../results/20260930T020846305626/) used dataset version `synthetic-eval-v1`, only seed 42, and 100 ticket rows per arm. Selected results:

| Arm | Mean network bytes/ticket | Messages/ticket | Recall@5 | MAP | Macro-F1 | Mean NAPFD | Rollback rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| A0 | 0 | 0 | 0.429 | 0.242 | 1.000 | 0.490 | 0.070 |
| A1 | 1,778 | 6 | 1.000 | 0.690 | 1.000 | 0.750 | 0.030 |
| A2 | 3,556 | 12 | 1.000 | 0.702 | 1.000 | 0.750 | 0.040 |
| A3 | 4,161 | 13 | 1.000 | 0.702 | 1.000 | 0.750 | 0.100 |

The injection summary recorded `20 blocked`, `0 passed`, meeting the synthetic target. All four arms reached macro-F1 of 1.0 because the generated severity text contains highly distinctive class phrases; this is a generator sanity check, not evidence of equivalent real-world classifier accuracy. A3 records more bytes than A2 because this harness includes a mobile bundle and aggregate return in addition to ACL messages. The wall-clock boxplot shows only tiny local workload timings and should not be interpreted as an operational latency comparison.

See the complete [BAB 9.4 report](../results/20260930T020846305626/BAB_9_4.md), [per-ticket data](../results/20260930T020846305626/per_ticket.csv), [per-stage data](../results/20260930T020846305626/per_stage.csv), and [security injection results](../results/20260930T020846305626/security_injection_summary.csv).

## 5. How to interpret and extend the results

The sample output verifies that the code paths run, the fixed seed 42 produces the intended synthetic inputs, and the stated policy checks block the included injection cases. It does **not** establish that a multi-agent architecture is faster, cheaper, safer, or more accurate on real enterprise tickets. In particular:

- synthetic severity phrases make the classification task unusually easy;
- duplicate reports are generated as near-copies and the harness retrieval proxy is lexical rather than the learned embedding/FAISS path;
- resource counts are simplified proxies; network bytes are serialized payload sizes, token counts are estimates, and deployment/DORA records are simulated;
- security injections cover four known patterns and do not constitute a broad adversarial security evaluation;
- seed 42 reproduces generated data and deterministic algorithmic decisions, but host timing and memory observations can vary.

For a stronger course experiment, replace the synthetic tickets with a versioned public/local export, preserve chronological train/validation/test boundaries, measure the same cases through the actual agent interfaces, log real message and mobile-runtime counters, and predefine an incident/deployment outcome record before calculating DORA-style metrics. Keep all raw production data on its source node and export only approved aggregate features.
