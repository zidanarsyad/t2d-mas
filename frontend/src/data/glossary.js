// Plain-language glossary. Each entry is {id, term, short (one sentence), example?, group}.
// <Term id="..."> shows `short` as a tooltip; Help lists every entry.

export const glossary = [
  // Messaging
  { id: "acl", group: "Messaging", term: "ACL message", short: "A structured message between agents: sender, receivers, a performative and the content.", example: "Broker-Triage informs Broker-Assign of the severity." },
  { id: "performative", group: "Messaging", term: "Performative", short: "The kind of message, such as inform (here is my result) or propose (here is my bid)." },
  { id: "contract-net", group: "Messaging", term: "Contract Net", short: "An auction: a broker calls for bids, workers propose, and the best bid wins the task." },
  { id: "utility", group: "Messaging", term: "Utility score", short: "How good a bid is: 0.5·skill + 0.3·(1 − workload) + 0.2·(1 − cost). Higher wins.", example: "Worker-Investigate wins with 0.69." },
  { id: "correlation-id", group: "Messaging", term: "Correlation id", short: "The ticket id every message carries, so one ticket's conversation can be followed." },
  // Gates and risk
  { id: "tau", group: "Gates and risk", term: "Confidence and τ", short: "The agent's confidence in its result; it may act alone only when confidence is at least τ." },
  { id: "risk-max", group: "Gates and risk", term: "Risk and R_max", short: "Each severity carries a risk; the agent may act alone only when the risk is at most R_max." },
  { id: "autonomy-gate", group: "Gates and risk", term: "Autonomy gate", short: "The rule confidence ≥ τ AND risk ≤ R_max. If either fails, a person decides." },
  { id: "human-gate", group: "Gates and risk", term: "Human checkpoint", short: "A point where the run pauses until a person approves, asks for changes or stops it." },
  { id: "duplicate-bands", group: "Gates and risk", term: "Duplicate detection", short: "Text similarity (cosine) to earlier tickets: high links automatically, middle asks a person, low means a new issue." },
  { id: "severity", group: "Gates and risk", term: "Severity", short: "How bad the problem is for users: Low, Medium, High or Critical." },
  { id: "canary", group: "Gates and risk", term: "Canary release", short: "Releasing to a small share of users first, watching the metrics, then widening step by step." },
  { id: "risk-score", group: "Gates and risk", term: "Release risk score", short: "A 0–1 estimate of how risky a release is, from change size, test results and history." },
  // Monitoring
  { id: "slo", group: "Monitoring", term: "SLO", short: "Service level objective: the limit a metric should stay under, such as p95 latency ≤ 800 ms." },
  { id: "p95", group: "Monitoring", term: "p95 latency", short: "95% of requests are faster than this; the slowest 5% are slower." },
  { id: "error-rate", group: "Monitoring", term: "Error rate", short: "The share of requests that fail." },
  { id: "anomaly", group: "Monitoring", term: "Anomaly (z-score)", short: "A value far from normal: z counts how many standard deviations it is from the baseline." },
  { id: "feedback-loop", group: "Monitoring", term: "Feedback loop", short: "Monitoring hands what it learns back to Triage, which can open a follow-up ticket." },
  // Mobile agents
  { id: "mobile-agent", group: "Mobile agents", term: "Mobile vs static agent", short: "A mobile agent travels to the data and runs there; a static agent stays put and pulls data to itself." },
  { id: "signed-bundle", group: "Mobile agents", term: "Signed bundle", short: "The mobile agent's code and state, signed so a node can check it was not changed on the way." },
  { id: "egress", group: "Mobile agents", term: "Aggregate and egress allowlist", short: "Only allow-listed summary fields may leave a node; raw logs and personal data stay there." },
  { id: "break-even", group: "Mobile agents", term: "Break-even and migrate rule", short: "Moving the agent saves bytes once a node holds more than bundle + result; the prototype migrates only above (bundle + result) × the policy factor." },
  // Metrics
  { id: "dora", group: "Metrics", term: "DORA metrics", short: "Five delivery measures: deployment frequency, lead time, change failure rate, recovery time and rework rate." },
  { id: "recovery-time", group: "Metrics", term: "Recovery time", short: "How long it takes to restore service after a failed deployment." },
  { id: "napfd", group: "Metrics", term: "NAPFD", short: "How early a test order finds the failing tests, from 0 to 1; higher is better." },
  { id: "macro-f1", group: "Metrics", term: "Macro-F1", short: "Severity accuracy averaged over the four classes, so rare classes count as much as common ones." },
  { id: "recall-at-5", group: "Metrics", term: "Recall@5", short: "How often the true duplicate appears among the first five suggestions." },
  { id: "arms", group: "Metrics", term: "A0–A3", short: "The four designs compared: A0 rules, A1 one agent, A2 specialist agents, A3 specialists with a mobile agent." },
  // Platform
  { id: "sse", group: "Platform", term: "SSE live updates", short: "Server-sent events: the backend pushes each stage, gate and message to the dashboard as it happens." },
  { id: "replay", group: "Platform", term: "Replay mode", short: "When the backend is not reachable, the dashboard plays recorded or illustrative data and labels it." },
  { id: "five-components", group: "Platform", term: "Five agent components", short: "Every stage agent runs perceive → remember → reason → act → report, and the dashboard shows each part." },
];

export const glossaryEntry = (id) => glossary.find((entry) => entry.id === id) || null;
