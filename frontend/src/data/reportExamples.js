// Illustrative numbers and texts from the report, kept apart from measured results.
// Anything shown from this file carries an "illustrative" label in the UI.

/** "Idea vs prototype": what the report designed and what this prototype really does. */
export const ideaVsPrototype = [
  { area: "Feedback capture", idea: "Many channels; normalise and mask personal data", prototype: "Inbox of real-style messages (Indonesian + English); masking is real", status: "real" },
  { area: "Duplicate detection", idea: "Similarity bands with a human in the middle", prototype: "Live TF-IDF cosine over character n-grams with three bands", status: "real" },
  { area: "Triage and autonomy gate", idea: "Severity score, then confidence ≥ τ and risk ≤ R_max", prototype: "Rule-based scoring (optional free LLM) and the same gate rule", status: "real" },
  { area: "Assignment", idea: "Contract Net auction", prototype: "Three squads bid; the winner investigates", status: "real" },
  { area: "Investigation", idea: "Mobile Scout-Log on the data nodes", prototype: "Real signed trips to six nodes; the node logs are seeded", status: "mixed" },
  { area: "Planning, implementation, QA", idea: "LLM planning, coding and CI", prototype: "Seeded simulators produce the plan, draft PR and CI result", status: "simulated" },
  { area: "Deployment", idea: "Canary, then a human release sign-off", prototype: "Risk score, canary and sign-off gates; deploys are simulated", status: "simulated" },
  { area: "Monitoring", idea: "SLO checks and a feedback loop", prototype: "Simulated telemetry with z-scores; an anomaly opens a follow-up ticket", status: "simulated" },
];

/** DORA cards for the Monitoring delivery report (illustrative sample, not measured). */
export const doraExample = [
  { id: "deploy-frequency", label: "Deployment frequency", value: "8.6", unit: "/ week", change: "+1.4", goodDirection: "up", note: "High performer band" },
  { id: "lead-time", label: "Lead time for changes", value: "3 h 42 min", unit: "", change: "−18%", goodDirection: "down", note: "Ticket to production" },
  { id: "change-failure", label: "Change failure rate", value: "4.1", unit: "%", change: "−1.2 pts", goodDirection: "down", note: "Target below 10%" },
  { id: "recovery", label: "Failed deploy recovery time", value: "26", unit: "min", change: "−8 min", goodDirection: "down", note: "Mean time to restore" },
  { id: "rework", label: "Rework rate", value: "7.8", unit: "%", change: "+0.6 pts", goodDirection: "down", note: "Changes needing follow-up" },
];

export const agentMetricsExample = [
  { id: "triage-accuracy", label: "Triage accuracy", value: "96.2%", change: "+2.4 pts", goodDirection: "up" },
  { id: "duplicate-recall", label: "Duplicates found · Recall@10", value: "91.4%", change: "+1.8 pts", goodDirection: "up" },
  { id: "token-cost", label: "Model cost per ticket", value: "$0.14", change: "−$0.03", goodDirection: "down" },
  { id: "human-override", label: "Human override rate", value: "6.8%", change: "−1.1 pts", goodDirection: "down" },
];

/** A seeded 30-day trend for the delivery report chart (illustrative). */
export const deliveryTrend = Array.from({ length: 30 }, (_, index) => ({
  day: `Sep ${index + 1}`,
  deploys: 5 + ((index * 7) % 8) + Math.floor(index / 8),
  lead: Number((5.8 - index * 0.073 + ((index % 5) - 2) * 0.13).toFixed(2)),
  failure: Number(Math.max(1.8, 7.6 - index * 0.14 + ((index % 6) - 3) * 0.23).toFixed(2)),
}));

/** The four designs compared in the evaluation (not four agent roles). */
export const armProcesses = [
  { id: "A0", name: "Rules and manual work", description: "Simple rules sort the issues; people handle the rest.", steps: ["Ticket arrives", "Rules check it", "People route and investigate", "People review key decisions"], note: "One process; no agent messages." },
  { id: "A1", name: "One assistant", description: "One AI assistant does every delivery task.", steps: ["Ticket arrives", "One assistant handles each task", "One recommendation", "People review key decisions"], note: "Tests whether one assistant is enough." },
  { id: "A2", name: "Specialist agents", description: "Separate agents for triage, investigation, QA and so on.", steps: ["Ticket arrives", "Specialists split the work", "Central system joins the results", "People review key decisions"], note: "Specialists stay central and exchange messages." },
  { id: "A3", name: "Specialists with a mobile agent", description: "Like A2, but Scout-Log investigates beside the log data.", steps: ["Ticket arrives", "Specialists split the work", "Scout-Log visits the data", "Summary returns for review"], note: "Only allow-listed summaries return; raw logs stay at the source." },
];
