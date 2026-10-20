// The agent team as designed in the report (§4). Runtime facts (status, load) come from
// live tickets; this file only describes roles. `components` explains the five parts every
// stage agent runs: perceive → remember → reason → act → report.

export const families = {
  Scout: "Collects information where it appears",
  Broker: "Coordinates decisions between agents",
  Worker: "Produces a specialist result",
  Security: "Enforces review and data rules",
};

export const agents = [
  {
    id: "Scout-Feedback", family: "Scout", mobility: "STATIC", stage: "intake",
    purpose: "Turns raw feedback from any channel into a clean ticket.",
    simulated: false,
    components: {
      perceive: "Reads the message, its channel and metadata.",
      remember: "Checks feedback it has already seen.",
      reason: "Finds the language, app version, device, component and steps to reproduce.",
      act: "Masks emails, phones and tokens, then writes the ticket.",
      report: "Hands the ticket to Broker-Triage.",
    },
  },
  {
    id: "Broker-Triage", family: "Broker", mobility: "STATIC", stage: "triage",
    purpose: "Scores severity, searches for duplicates and applies the autonomy gate.",
    simulated: false,
    components: {
      perceive: "Reads the ticket text, including Indonesian slang.",
      remember: "Compares it with earlier tickets (TF-IDF cosine).",
      reason: "Scores severity and confidence; picks a duplicate band.",
      act: "Links a duplicate, continues, or pauses for a person.",
      report: "Explains the score, the cues and the gate result.",
    },
  },
  {
    id: "Broker-Assign", family: "Broker", mobility: "STATIC", stage: "assignment",
    purpose: "Runs the Contract Net auction between the investigation squads.",
    simulated: false,
    components: {
      perceive: "Reads the component and severity.",
      remember: "Counts each squad's open tickets.",
      reason: "Scores bids: 0.5·skill + 0.3·(1 − load) + 0.2·(1 − cost).",
      act: "Sends the call for bids, accepts the best and declines the rest.",
      report: "Names the winner, its utility and the SLA due time.",
    },
  },
  {
    id: "Worker-Investigate", family: "Worker", mobility: "STATIC", stage: "investigation",
    purpose: "The winning squad investigates with help from the mobile Scout-Log.",
    simulated: "mixed",
    squads: ["Worker-Investigate-Payments", "Worker-Investigate-Mobile", "Worker-Investigate-Platform"],
    components: {
      perceive: "Reads the ticket and the suspect component.",
      remember: "Looks up the service call chain.",
      reason: "Ranks suspect services from the node aggregates.",
      act: "Sends Scout-Log to each node that is worth visiting.",
      report: "Gives a hypothesis and reproduction steps (not a confirmed root cause).",
    },
  },
  {
    id: "Scout-Log", family: "Scout", mobility: "MOBILE", stage: "investigation",
    purpose: "Travels to the data nodes as a signed bundle and brings back only aggregates.",
    simulated: "mixed",
    components: {
      perceive: "Reads how much log data each node holds.",
      remember: "Carries its state inside the signed bundle.",
      reason: "Migrates only when the node holds more than (bundle + result) × factor.",
      act: "Runs the analysis in the node's sandbox.",
      report: "Returns allow-listed aggregate fields; raw logs stay on the node.",
    },
  },
  {
    id: "Worker-Plan", family: "Worker", mobility: "STATIC", stage: "planning",
    purpose: "Turns the investigation into tasks, acceptance criteria and an estimate.",
    simulated: true,
    components: {
      perceive: "Reads the hypothesis and the affected service.",
      remember: "Checks the sprint board's remaining capacity.",
      reason: "Splits the fix into subtasks with estimates.",
      act: "Writes Given/When/Then acceptance criteria.",
      report: "Says whether the work fits the current sprint.",
    },
  },
  {
    id: "Worker-Impl", family: "Worker", mobility: "MOBILE", stage: "implementation",
    purpose: "Drafts the change as a pull request (simulated) and runs a secret scan.",
    simulated: true,
    components: {
      perceive: "Reads the plan and the repository context.",
      remember: "Finds the files the service owns.",
      reason: "Decides which files and tests to touch.",
      act: "Writes a draft diff and records it; nothing is merged.",
      report: "Shows the diff summary and the secret-scan result.",
    },
  },
  {
    id: "Worker-QA", family: "Worker", mobility: "STATIC", stage: "qa",
    purpose: "Chooses the riskiest tests that fit the CI budget and scores the order.",
    simulated: true,
    components: {
      perceive: "Reads the changed files.",
      remember: "Loads the test catalogue and past failures.",
      reason: "Ranks tests by risk and fits them into the time budget.",
      act: "Runs the selection on a simulated CI.",
      report: "Gives NAPFD, pass/fail and asks for a code review.",
    },
  },
  {
    id: "Worker-Deploy", family: "Worker", mobility: "STATIC", stage: "deployment",
    purpose: "Scores release risk, runs a small canary and prepares the full release.",
    simulated: true,
    components: {
      perceive: "Reads the QA result and the change size.",
      remember: "Checks the deployment history.",
      reason: "Computes the release risk score.",
      act: "Starts a 5% canary when the risk is low; otherwise asks a person.",
      report: "Shows the canary result and waits for the release sign-off.",
    },
  },
  {
    id: "Scout-Monitor", family: "Scout", mobility: "MOBILE", stage: "monitoring",
    purpose: "Watches the release against SLO baselines and closes the feedback loop.",
    simulated: true,
    components: {
      perceive: "Collects post-release metrics.",
      remember: "Loads the SLO baseline for the service.",
      reason: "Computes z-scores against the baseline.",
      act: "Opens a follow-up ticket when a metric breaks the SLO.",
      report: "Updates the baseline and hands the result back to Triage.",
    },
  },
  {
    id: "Security-Policy", family: "Security", mobility: "STATIC", stage: null,
    purpose: "Checks every gate, signs mobile bundles and blocks secrets and raw data from leaving.",
    simulated: false,
    components: {
      perceive: "Sees every gate decision and message.",
      remember: "Writes the append-only audit log.",
      reason: "Applies τ, R_max and the egress allowlist.",
      act: "Blocks merges and full releases without a recorded human approval.",
      report: "Explains which rule passed or failed.",
    },
  },
];

export const agentInfo = (id) => {
  const value = String(id || "");
  return agents.find((agent) => agent.id === value) || (value.startsWith("Worker-Investigate") ? agents.find((agent) => agent.id === "Worker-Investigate") : null);
};
