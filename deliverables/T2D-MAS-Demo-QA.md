# T2D-MAS demo: questions and answers

Questions the lecturer or the audience are likely to ask, with short answers you can say aloud.
The answers match the code, the evaluation run the report cites
(`results/20260930T020846305626`) and the report as exported on 21 October 2026. Where the
dashboard can back an answer up, **Show** says where to look.

Read *Numbers to know* first. The mobile-agent questions come early because the course currently
focuses on mobile agents. *Say it precisely* at the end lists the claims to avoid.

## Numbers to know

| Topic | Value |
|---|---|
| Autonomy gate | Act alone only if confidence ≥ τ = 0.70 **and** risk ≤ R_max = 0.60 |
| Risk by severity | Low 0.1 · Medium 0.3 · High 0.6 · Critical 1.0 |
| Duplicate bands | ≥ 0.85 link · 0.70–0.85 a person decides · < 0.70 new ticket |
| Contract Net | U = 0.5·skill + 0.3·(1 − load) + 0.2·(1 − cost). FB-001 on a fresh board: Payments 0.87, Platform 0.70, Mobile app 0.67 |
| SLA | Critical 2 h · High 8 h · Medium 72 h · Low 168 h |
| Migration rule | Ship the agent when L > (A + R) × k = (12 + 2) × 3 = 42 MB; break-even 14 MB |
| Live trip | 2.11 KB bundle per node · 11.5 KB in total · node-6 (30 MB) answers through its exporter |
| Cost model (TCK-1042) | Static pull 8,190 MB in ≈ 10 min 55 s · mobile agent 84 MB in ≈ 27 s · 98.97% fewer bytes, ≈ 24× faster |
| QA | About 100 of 3,400 tests in an 8-minute budget, scored with NAPFD |
| Release risk | 0.30·change size + 0.30·QA failure rate + 0.15·critical service + 0.25·rollback history; the 5% canary starts alone only at ≤ 0.30 |
| Monitoring | Anomaly at z ≥ 3 or an SLO breach |
| Evaluation | A0–A3 on the same 500 tickets: 100 generated tickets × 5 seeds (42–46) |
| Results | Recall@5 0.429 → 1.000 · NAPFD 0.49 → 0.75 · bytes per ticket A2 3,556, A3 4,161 · rollback A0–A3 5.6 / 5.4 / 5.8 / 7.4% |
| Statistics | Friedman: bytes p = 0.0018, wall time p = 0.0136, CPU p = 0.926, rollback p = 0.604 |
| Security | 20 of 20 injected policy violations blocked; 0 full releases without approval |
| Tests | 55 backend and 63 dashboard tests, run by GitHub on every push |

## 1. The idea

**What problem does T2D-MAS solve?**
Software teams lose time between a user's complaint and a safe fix in four places: manual
triage, duplicate reports, approval queues and tickets of uneven quality. T2D-MAS hands each
step to a specialist agent, from the first complaint to a monitored release, and keeps people in
control of high-risk decisions.

**Who would use it?**
A product or support team that receives feedback, the developers who fix it, and the reviewers
and release managers who approve risky steps. In the demo, you play the reviewer.

**Why a multi-agent system, and not one model or one service?**
Each decision has a different input, owner and risk. As separate agents, every decision stays
small and explainable, each risky step gets its own gate, work goes to the best-placed squad at
run time (the Contract Net), and analysis code can move to the data (the mobile agent). Be
careful with the evaluation, though: the multi-agent set-ups do not beat the single agent on
accuracy. See *Did the multi-agent set-ups beat the single agent?* in section 6.

## 2. Mobile agents (the course focus)

**What is the mobile agent, and why use one here?**
Scout-Log. A crash investigation needs the services' logs, which are large and contain personal
data. Instead of pulling every log to one server, Scout-Log carries its analysis code to each of
the six data nodes, runs it next to the logs and brings back only a few numbers.
*Show:* Agents → Scout-Log → *The mobile agent at work*.

**What exactly moves?**
A signed bundle: the analysis program's source code, its state (seed, product area and a
30-minute window) and an Ed25519 signature. In the live trip it is 2.11 KB per node, and about
150 bytes come back.

**Weak or strong mobility?**
Weak. The code and its data state move, and execution starts fresh on the node. Strong mobility
would also move the running program's execution state, which standard Python cannot serialize.
Aglets, a classic Java platform, also uses weak mobility.

**How does it decide whether to move?**
Before each visit it asks the node how much log data it holds. It ships the agent only when the
node holds more than (A + R) × k = (12 + 2) × 3 = 42 MB, where A is the bundle size, R the
result size and k a safety factor. Moving pays off above 14 MB (the break-even), and k = 3 leaves
a margin for wrong size estimates. node-6 holds 30 MB, so its built-in exporter answers instead.

**Your bundle is 2 KB. Why does the rule assume 12 MB?**
The policy uses the report's planning sizes, so the live decisions match the report's worked
example. With the real 2 KB bundle, the agent would move to every node, node-6 included.

**Is it really a mobile agent, or just remote execution?**
It carries its own code and state to the data and decides per node whether moving pays off.
Each trip is one hop, in the master–slave pattern: Worker-Investigate sends Scout-Log out and
collects the results. A multi-hop itinerary (node to node, carrying partial results) would be the
next step. The node's exporter is the client–server alternative, and it can only answer the
questions its owner installed in advance.

**How does a node protect itself from a bad agent?**
Three checks:
- **Signature.** Only the orchestrator holds the private key; the nodes get the public key. A unit test shows that an altered bundle fails verification.
- **Isolated process.** The code runs in a separate Python process: standard library only, a 20-second limit, never written to disk.
- **Egress allowlist.** Only allowlisted aggregate fields may leave. The node checks them, and the orchestrator checks again.

Every migration is also written to the audit log.

**What protects the agent from a dishonest node?**
Nothing yet. The prototype assumes the data nodes are the company's own servers. Known defences,
such as sending several agents and voting, signed partial results or trusted hardware, are
future work.

**What if a node is down?**
That visit is marked failed, and the investigation continues with the nodes that answered.

**Are the six nodes real?**
In local mode, which the demo uses, they are the real node program running inside the backend
process, reached through in-memory HTTP. The signing, the isolated process and the allowlist are
the real code. With Docker, each node is its own container. The node logs are seeded test data
(600 rows per node, with fake customer e-mails); 1,365 MB is the report's nominal size.

**Did the experiment show that mobile agents save traffic?**
No. In the benchmark, A3 (with the mobile agent) sent more bytes per ticket than A2 (static
agents): 4,161 against 3,556. The generated tickets carry almost no log data, so the bundle is
pure overhead, which is what the break-even rule predicts below 14 MB per node. The 98.97% saving
comes from the report's cost model for 1,365 MB per node; it is not a measurement.
*Show:* Experiment results, *Data sent per ticket*.

**Worker-Impl and Scout-Monitor are labelled Mobile. Do they move?**
Not in this prototype. The report designs them as mobile, but here they run as simulators. Only
Scout-Log travels.

**Why not JADE or another agent platform?**
The rest of the project is Python (FastAPI, NumPy, and PyTorch for the offline models), so we
built a small agent host instead: each node is a FastAPI app with `/inventory`, `/execute` and
`/aggregates`. We kept the FIPA ideas this system needs: ACL messages and the Contract Net. A
platform such as JADE would add standard directory and mobility services, but split the code
across two languages.

**Why use mobile agents at all?**
Lange and Oshima's seven reasons, checked against this prototype:
- **Reduce network load:** yes, when nodes hold large logs.
- **Overcome network latency:** partly. One round trip per node replaces streaming the logs.
- **Encapsulate protocols:** yes. The bundle brings its own analysis.
- **Execute asynchronously and autonomously:** partly. The orchestrator waits for each reply.
- **Adapt dynamically:** yes. The rule is applied per node.
- **Run on heterogeneous hosts:** partly. Every node needs Python.
- **Be robust and fault-tolerant:** partly. A failed node is skipped.

## 3. Agents and how they work together

**Which agents are there?**
Nine stage agents in four families: Scouts collect, Brokers decide where work goes, Workers do
the work, and Security enforces policy. They are Scout-Feedback, Broker-Triage, Broker-Assign,
Worker-Investigate, Worker-Plan, Worker-Impl, Worker-QA, Worker-Deploy and Scout-Monitor. With
Scout-Log, the mobile agent, and Security-Policy, which runs every gate, the Agents page lists
eleven.

**What makes them agents rather than functions?**
Each runs the report's five-step loop: perceive, remember, reason, act, report. They keep state
(earlier tickets, SLO baselines, the squads' load), act on their own inside limits that the gates
set, and talk through ACL messages. Some take the initiative: Scout-Monitor opens a follow-up
ticket by itself when a release goes bad. Their autonomy is bounded on purpose: when a rule
fails, they stop and ask a person.
*Show:* every stage in **Run a ticket** lists its five steps.

**How do the agents communicate?**
With FIPA-ACL-style messages on a message bus: Redis Streams with Docker, an in-memory bus in
local mode. The Contract Net uses `cfp`, `propose`, `accept-proposal` and `reject-proposal`, and
each stage hands its result to the next with `inform`. Every message records the τ and R_max it
ran under. Shared state sits on a blackboard: PostgreSQL with Docker, memory in local mode.
*Show:* Decision trace.

**How does the Contract Net work?**
Broker-Assign sends a call for proposals to three squads: Payments, Mobile app and Platform. Each
bids U = 0.5·skill + 0.3·(1 − load) + 0.2·(1 − cost), using its skill for the product area and
its current load. The highest bid wins and investigates, and the SLA follows the severity.

For FB-001 on a fresh board, Payments bids 0.5 × 0.92 + 0.3 × (1 − 0.1) + 0.2 × (1 − 0.3) = 0.87,
against 0.70 for Platform and 0.67 for Mobile app. Payments wins, and the Critical SLA is 2 hours.
*Show:* Decision trace → *Call for bids* shows the bid table.

**Why those weights?**
They are the report's design values (equation 13): skill matters most, then current load, then
cost. They are not learned; tuning or learning them is future work.

## 4. Autonomy, gates and safety

**When may an agent act alone?**
Only when its confidence is at least τ = 0.70 **and** the risk is at most R_max = 0.60. Risk
comes from the severity: Low 0.1, Medium 0.3, High 0.6, Critical 1.0. So a Critical issue always
goes to a person, and a High one passes only when the agent is confident.

**Why 0.70 and 0.60?**
They are the report's design values. With that risk table, every Critical issue and every
low-confidence decision goes to a person. Both values live in one policy module and the
`policies` table, so they can change without code changes. We did not tune them on real data.

**What are the six gates?**
Merge review and release sign-off always ask a person, because both are irreversible. Four more
stop only when their rule fires:
- **Duplicate review:** similarity between 0.70 and 0.85.
- **Autonomy gate:** low confidence or high risk at triage.
- **Secret scan:** a secret in the draft change. It can only be redrafted or stopped, never approved.
- **Canary review:** a release risk above 0.30.

*Show:* Human reviews, the gate table at the bottom.

**Can an agent merge or deploy without a person?**
No. This rule is enforced in three places: the orchestrator; the function that carries out
irreversible actions, which checks the recorded approval; and the database, where triggers
reject a merge or a deployment without `human_approved`. Tests check these guards.

**How do you keep the audit log trustworthy?**
It is append-only: in PostgreSQL, triggers block UPDATE, DELETE and TRUNCATE. Every stage output,
gate decision, message, approval and blocked action is logged, with the values it was checked
against.
*Show:* Tickets → Saved runs.

**What about personal data?**
Scout-Feedback masks e-mail addresses, phone numbers and tokens before anything is stored, and
reviewer notes are masked too. Raw logs never leave the data nodes; only allowlisted aggregates
do.

**What does the LLM do, and can it approve anything?**
It is optional: a free OpenRouter model can propose a severity and structure a reviewer's note.
Its confidence is capped at 0.69, just below τ, so its proposals always reach a person. It never
approves anything. Without a key, or when the model fails, the local rules take over. The demo
runs without a key, so it behaves the same every time.

**Who approves? Is there a login?**
The reviewer types a name and a reason, and both are recorded. There is no login, so the name is
not an authenticated identity; a real deployment would need one.

## 5. AI and data

**How does triage judge severity?**
With impact rules in English and Indonesian, including common slang, so a casual Indonesian
message is understood. The optional LLM can propose a severity instead, under the cap above.

**How does duplicate detection work?**
TF-IDF cosine similarity over character n-grams, against earlier tickets. Character n-grams
tolerate typos and slang. It reproduces the idea document's example (0.994 for the duplicate
pair, 0.119 for the unrelated one), and FB-002 matches FB-001 at 0.956. Its weakness: it misses
an Indonesian and an English report of the same problem.
*Show:* run FB-002 after FB-001.

**How does the investigation find the likely cause?**
The aggregates from the nodes become z-scores against each service's SLO baseline, for latency
and error rate. One GraphSAGE-mean pass over the call chain mixes each service's anomaly with its
neighbours', so the source of a cascade ranks first. For FB-001 that is payment-db. The trained
GraphSAGE model, GNNExplainer and PageRank stay offline in `rca/`.

**How does QA choose tests?**
It ranks the tests by 0.5·failure history + 0.3·closeness to the changed service + 0.2·recent
failures, then takes as many as fit an 8-minute budget: about 100 of 3,400. NAPFD (0 to 1) scores
how early the failing tests run. The CI run itself is simulated.

**How is the release risk computed?**
0.30·change size + 0.30·QA failure rate + 0.15·critical-service flag + 0.25·rollback history. At
0.30 or less the 5% canary starts by itself; above that, a person approves it. The full release
always needs a sign-off, and an SLO breach rolls back automatically.

**Where are the machine learning, deep learning and reinforcement learning?**
In offline modules: MiniLM + FAISS and DistilBERT for triage, a trained GraphSAGE model for root
causes, and PPO/DQN policies for test ordering and canary releases. The live demo uses their
simpler, explainable counterparts. The benchmark's severity ROC uses TF-IDF with a calibrated
LinearSVC.

**What data did you use?**
The benchmark uses generated tickets (`synthetic-eval-v1`): 100 per seed, five seeds. The demo
inbox holds 42 realistic messages in Indonesian and English, with fake personal data. Loaders for
public bug data (GitBugs, Eclipse and Mozilla exports) exist, but the reported results do not use
them.

## 6. Evaluation

**What did you compare?**
Four set-ups on the same 500 generated tickets: A0, rules in one process; A1, a single agent; A2,
several static agents; A3, several agents plus the mobile agent.

**What are the main results?**
- The agent set-ups beat the rule baseline at finding duplicates (Recall@5 0.429 → 1.000) and at ordering tests (NAPFD 0.49 → 0.75).
- A3 sends the most data (4,161 bytes per ticket, against 3,556 for A2).
- A3 also has the highest simulated rollback rate (7.4%), but that difference is not significant (Friedman p = 0.604).
- All 20 injected policy violations were blocked, and no full release ran without approval.

*Show:* Experiment results, saved run of 30 Sep 2026.

**Did the multi-agent set-ups beat the single agent?**
Not on accuracy. A1, A2 and A3 have the same Recall@5 (1.000), almost the same MAP (0.680, 0.687,
0.685) and the same NAPFD (0.75). What the multi-agent design adds in this prototype is
structure: separate owners and gates for risky steps, an audit trail per decision, assignment at
run time, and code that can move to the data. Showing a quality gain needs real data.

**Why is severity Macro-F1 1.0 everywhere?**
A label leak: every generated ticket title contains its severity phrase ("critical data loss",
"minor cosmetic"). We report it as a limitation, not a result. Fixing it needs new evaluation
tickets, which would change every number in the report.

**Are the differences significant?**
Across the four set-ups, the Friedman test is significant for data sent (p = 0.0018) and wall
time (p = 0.0136), but not for CPU (p = 0.926) or rollback (p = 0.604). With only five seeds, a
paired Wilcoxon test cannot go below p = 0.0625, so no pairwise Wilcoxon test reaches 0.05. The
Nemenyi post-hoc test does separate A0 from A3 on data sent (Holm-adjusted p = 0.008).

**Why only five seeds, and why generated data?**
Generated data lets every number be reproduced from a seed, one of the project's four rules, and
gives every set-up identical tickets. Five seeds fit the course's time. The cost is statistical
power and realism, which is why the deck calls these classroom results, not field evidence.

**Are the timings meaningful?**
Only as relative workload proxies. They are fractions of a millisecond per ticket on one laptop,
not service latency, and they vary between machines.

**Can someone reproduce the numbers?**
Yes. `python -m eval.runner --config eval/config.json` creates a new run, and
`python -m eval.compare_runs` checks it against the cited run. Every column matches except four
that depend on the machine: wall time, CPU time, memory, and the lead time derived from wall
time.

**Are the DORA metrics real?**
No. Deployment frequency, lead time, recovery time and change failure rate are simulated, and the
dashboard labels them as illustrative.

## 7. Real, simulated, and what comes next

**What is real and what is simulated?**
Real: feedback capture and masking, duplicate search, triage and the autonomy gate, the Contract
Net, the mobile trips with their signing and egress checks, the six gates and the audit log.
Simulated with seeds: the node logs, the project board, the repository and draft change, CI,
deployments and telemetry. Every panel in the dashboard says which.
*Show:* Overview → *Idea vs prototype*.

**Is it production-ready?**
No. It is a course prototype. It does not touch a real repository, CI, cluster or telemetry, it
has no login, and the report's 30-second undo window is not built.

**What are the main limitations?**
- Simulators stand in for every external system.
- The benchmark's severity labels leak, and its duplicate metrics use a word-overlap stand-in.
- Lexical duplicate search misses Indonesian–English pairs.
- The triage rules were tuned on the same demo messages they run on.
- The node's isolated process is not a hardened sandbox, and a dishonest node is not handled.

**What would you do next?**
- Replace the simulators with a real repository, CI, release pipeline and telemetry.
- Move the offline models (MiniLM + FAISS, the trained GraphSAGE, the RL policies) into the live path.
- Evaluate on public bug data, with new tickets that do not leak their labels.
- Give the mobile agent a multi-hop itinerary and protection against dishonest nodes.

## 8. If something unexpected happens during the demo

- **The canary gate did not appear.** The release risk was 0.30 or less, so the 5% canary started by itself. The gate appears only on some runs.
- **A message went straight to "Linked as a duplicate".** It already ran on this backend. Local mode remembers it until the backend restarts.
- **The release risk changed between runs.** The simulators are seeded from the ticket id, and every run gets a new id.
- **The badge says Replay mode.** The dashboard cannot reach the backend. Overview, Decision trace, Agents and Monitoring keep playing their recorded or simulated versions; restart the backend.
- **"Can you show it with Docker?"** `docker compose up --build` starts the orchestrator, six node containers, Redis and PostgreSQL. The demo uses local mode because it needs no services and runs the same node code.

## Say it precisely

- The 98.97% and 24× figures come from the cost model; they were not measured.
- The benchmark shows that the agent set-ups beat the rule baseline, not that several agents beat one.
- Macro-F1 = 1.0 comes from a label leak, not from good classification.
- In local mode the six nodes run inside the backend process, not on separate machines.
- The node's isolated process is a safeguard, not a hardened sandbox. The signature decides which code runs.
- Only Scout-Log migrates.
- Planning, implementation, QA, deployment and monitoring run on seeded simulators. Nothing touches a real repository or cluster.
- The LLM is optional and never approves anything.
