# Agent catalog

Each agent follows the report's five components (§5.3.1): it **perceives** its input,
**remembers** what it needs from the shared blackboard, **reasons** about a decision, **acts**
through tools, and **reports** a result. Every stage output in the dashboard shows these five
steps in plain language. The families follow the report: Scouts collect, Brokers decide where
work goes, Workers do the work, and Security enforces policy.

| Stage | Agent (family, mobility) | What it does | Real or simulated |
|---|---|---|---|
| 1 Feedback capture | **Scout-Feedback** (Scout, static) | Reads a user message from any channel (app review, e-mail, portal, CS chat, Slack, crash report). Masks e-mails, phone numbers and tokens. Detects the language (Indonesian / English / mixed). Derives a title. Extracts the app version, device and reproduction hints. Guesses the product area. | Real. Rules over the text. |
| 2 Triage | **Broker-Triage** (Broker, static) | Searches earlier tickets for duplicates: TF-IDF cosine over character n-grams, ≥ 0.85 links, 0.70–0.85 asks a person. Judges severity with English and Indonesian impact rules, optionally with a free OpenRouter model. Applies the autonomy gate. | Real |
| 2 Assignment | **Broker-Assign** (Broker, static) | Runs a Contract Net auction: three investigation squads (Payments, Mobile app, Platform) bid with utility = 0.5·skill + 0.3·(1 − load) + 0.2·(1 − cost). The winner takes the ticket. Sets the SLA from the severity. | Real |
| 3 Investigation | **Worker-Investigate-<squad>** (Worker, static) with **Scout-Log** (Scout, mobile) | Scout-Log visits the six data nodes. Where a node holds more than (12 + 2) × 3 = 42 MB of logs, it ships signed analysis code there; otherwise it asks the node's exporter. Only aggregates come back. The investigator ranks the services on the call chain with the report's GraphSAGE-mean calculation (`rca/numerics.py`) and writes a hypothesis. | Mixed. The node trips, signatures and egress checks are real; the node logs are simulated. |
| 4 Planning | **Worker-Plan** (Worker, static) | Splits the fix into subtasks with estimates and Given/When/Then acceptance criteria. Checks sprint capacity. | Simulated project board |
| 5 Implementation | **Worker-Impl** (Worker, mobile) | Drafts a pull request for the suspected service. **Security-Policy** scans the draft for secrets; a secret blocks it until it is redrafted. | Simulated repository; the secret scan is real |
| 6 QA | **Worker-QA** (Worker, static) | Picks the riskiest tests that fit an 8-minute budget (about 100 of 3,400) and reports NAPFD. Merging needs a code review. | Simulated CI; the selection and NAPFD maths are real |
| 7 Deployment | **Worker-Deploy** (Worker, static) | Computes a release risk score. Runs a 5% canary on its own only if the score is ≤ 0.30, otherwise asks a person. The full release always needs a sign-off, and an SLO breach rolls back automatically. | Simulated deploy pipeline; the rules are real |
| 8–9 Monitoring and feedback loop | **Scout-Monitor** (Scout, mobile) | Compares post-release metrics with the SLO baselines (z-score ≥ 3 or an SLO breach). A healthy release updates the baseline; an anomaly opens a follow-up ticket that goes back to triage. | Simulated telemetry |
| All gates | **Security-Policy** (Security) | Evaluates every gate, scans drafts for secrets, signs and checks mobile bundles, allowlists node results, and writes the audit log. | Real |

## Gates (where a person decides)

| Gate | Stops when | Approve | Request changes | Reject |
|---|---|---|---|---|
| `duplicate_review` | Similarity 0.70–0.85 | Link and close | Keep it as a new ticket | Stop |
| `autonomy_gate` | Confidence < τ (0.70) or risk > R_max (0.60) | Continue | Re-triage with the reviewer's note | Stop |
| `secret_scan` | A secret is found in the draft | Not allowed | Redraft without it | Stop |
| `pr_merge` | Always | Merge (recorded, needs this approval) | QA adds the requested checks | Stop |
| `canary_review` | Release risk > 0.30 | Run the 5% canary | Record constraints, ask again | Stop |
| `release_signoff` | Always | Full deploy (recorded, needs this approval) | Record constraints, ask again | Stop |

A reason is required for every review. Notes are masked before they are stored. In local mode
without an OpenRouter key, a triage change request is applied only when it states the new
severity explicitly ("severity should be High"). Otherwise the run asks for clarification.

## What is not built

- **No real systems.** The prototype does not edit a real repository, run a real CI suite or deploy to a real cluster. Those tools are simulated, and the outputs say so.
- **No live models.** The trained models stay offline: the MiniLM+FAISS duplicate model in `triage/`, the GraphSAGE model in `rca/` and the PPO/DQN policies in `envs/`. The live demo uses their simpler, explainable counterparts.
- **No undo window.** The report's 30-second undo for autonomous actions is not implemented.
