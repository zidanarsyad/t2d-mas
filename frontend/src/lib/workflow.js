// The one list of pipeline stages, human gates and plain-language labels.
// Pure JS (no React, no DOM), so `node --test` can load it directly.

/** The nine stages in backend order. `plain` is the short subtitle shown under the name. */
export const stages = [
  {
    id: "intake",
    name: "Feedback capture",
    plain: "Read and tidy the feedback",
    agent: "Scout-Feedback",
    phase: "understand",
    description:
      "Turns a user message into a ticket: title, app version, device and steps, with personal data masked.",
  },
  {
    id: "triage",
    name: "Triage",
    plain: "Judge severity, spot duplicates",
    agent: "Broker-Triage",
    phase: "understand",
    description:
      "Scores the severity, searches for duplicates and asks a person when confidence is low or risk is high.",
  },
  {
    id: "assignment",
    name: "Assignment",
    plain: "Pick the best squad",
    agent: "Broker-Assign",
    phase: "understand",
    description:
      "Runs a Contract Net auction: squads bid with skill, workload and cost, and the highest utility wins.",
  },
  {
    id: "investigation",
    name: "Investigation",
    plain: "Find the likely cause",
    agent: "Worker-Investigate",
    phase: "understand",
    description:
      "Sends the mobile Scout-Log to the data nodes and ranks the suspect services from the aggregates it brings back.",
  },
  {
    id: "planning",
    name: "Planning",
    plain: "Break the fix into tasks",
    agent: "Worker-Plan",
    phase: "fix",
    description: "Writes subtasks, Given/When/Then acceptance criteria and an estimate.",
  },
  {
    id: "implementation",
    name: "Implementation",
    plain: "Draft the change",
    agent: "Worker-Impl",
    phase: "fix",
    description: "Drafts a pull request (simulated) and scans it for secrets before anyone sees it.",
  },
  {
    id: "qa",
    name: "QA",
    plain: "Run the riskiest tests first",
    agent: "Worker-QA",
    phase: "fix",
    description: "Picks tests within the CI time budget, scores the order with NAPFD and asks for a code review.",
  },
  {
    id: "deployment",
    name: "Deployment",
    plain: "Release in small steps",
    agent: "Worker-Deploy",
    phase: "release",
    description: "Scores the release risk, runs a small canary and waits for a release sign-off.",
  },
  {
    id: "monitoring",
    name: "Monitoring",
    plain: "Watch and learn",
    agent: "Scout-Monitor",
    phase: "release",
    description:
      "Compares post-release metrics with SLO baselines and opens a follow-up ticket when something breaks.",
  },
];

/** Older name for the same list, kept so existing imports and tests keep working. */
export const workflow = stages;
export const stageIds = stages.map((stage) => stage.id);

export const phases = [
  { id: "understand", name: "Understand the report", description: "Turn feedback into a clear piece of work." },
  { id: "fix", name: "Prepare and check a fix", description: "Specialists draft a change and choose the tests." },
  { id: "release", name: "Release and learn", description: "People sign off releases; monitoring feeds back." },
];

export function stageInfo(id) {
  return (
    stages.find((stage) => stage.id === id) || {
      id,
      name: id ? String(id).replaceAll("_", " ") : "Workflow",
      plain: "",
      agent: "Orchestrator",
      phase: null,
      description: "",
    }
  );
}

/**
 * The six human gates. Labels here are fallbacks: the live labels come from GET /policy.
 * `conditional` gates only pause when a rule fails; the others always pause.
 */
export const gates = [
  { id: "duplicate_review", label: "Confirm the duplicate", stage: "triage", agent: "Broker-Triage", conditional: true, irreversible: false },
  { id: "autonomy_gate", label: "Confirm the impact assessment", stage: "triage", agent: "Broker-Triage", conditional: true, irreversible: false },
  { id: "secret_scan", label: "Remove a secret from the change", stage: "implementation", agent: "Security-Policy", conditional: true, irreversible: false },
  { id: "pr_merge", label: "Review the proposed change", stage: "qa", agent: "Worker-QA", conditional: false, irreversible: true },
  { id: "canary_review", label: "Approve the canary", stage: "deployment", agent: "Worker-Deploy", conditional: true, irreversible: false },
  { id: "release_signoff", label: "Approve the full release", stage: "deployment", agent: "Worker-Deploy", conditional: false, irreversible: true },
];

export function gateInfo(id) {
  return gates.find((gate) => gate.id === id) || null;
}

/** The gate a stage usually waits at, used when a message does not name it. */
export const defaultGateForStage = {
  triage: "autonomy_gate",
  implementation: "secret_scan",
  qa: "pr_merge",
  deployment: "release_signoff",
};

/** What each review button does at each gate (the reject button always stops the run). */
export const intentEffects = {
  duplicate_review: { accept: "Link it to the existing ticket and close this run", request_changes: "Treat it as a new ticket" },
  autonomy_gate: {
    accept: "Continue with this assessment",
    request_changes: "Re-run triage with your note (without the language model, name the severity, e.g. “severity should be High”)",
  },
  secret_scan: { accept: "Not allowed while a secret is in the change", request_changes: "Redraft the change without the secret" },
  pr_merge: { accept: "Merge the change (irreversible, audited)", request_changes: "Add checks and re-run QA" },
  canary_review: { accept: "Start the canary", request_changes: "Add constraints to the release plan" },
  release_signoff: { accept: "Deploy to everyone (irreversible, audited)", request_changes: "Add constraints to the release plan" },
};
export const INTENTS = ["accept", "request_changes", "reject"];
export const intentLabel = { accept: "Approve", request_changes: "Request changes", reject: "Reject and stop" };

export function statusLabel(status) {
  return (
    {
      running: "In progress",
      waiting_for_review: "Waiting for a human",
      completed: "Finished (prototype)",
      rejected: "Stopped by reviewer",
      duplicate: "Linked as duplicate",
    }[status] || (status ? String(status).replaceAll("_", " ") : "Unknown")
  );
}

/** Words for the stage states drawn by the animated flow. */
export const stateLabel = {
  done: "Done",
  active: "Current",
  waiting: "Waiting for a human",
  revising: "Revising",
  stopped: "Stopped",
  upcoming: "Upcoming",
  skipped: "Skipped",
};

/** Plain names for ACL performatives; the raw name is shown small next to them. */
export function performativeLabel(value) {
  return (
    {
      cfp: "Call for bids",
      propose: "Bid",
      "accept-proposal": "Bid accepted",
      "reject-proposal": "Bid declined",
      inform: "Result shared",
      refuse: "Declined",
      failure: "Problem reported",
    }[value] || value || "Message"
  );
}
export const messageLabel = performativeLabel;

export function recipients(message) {
  const value = message?.receiver || message?.receivers || [];
  return Array.isArray(value) ? value : [value];
}

const AGENT_PREFIXES = ["Scout-", "Broker-", "Worker-", "Security-", "Orchestrator", "Human-"];

/** True for the agent ids the backend uses; anything else (a reviewer's name) is a person. */
export function isAgentName(name) {
  return AGENT_PREFIXES.some((prefix) => String(name || "").startsWith(prefix));
}

/** The stage an agent works on; the three investigation squads all map to Investigation. */
export function stageOfAgent(name) {
  const value = String(name || "");
  if (value.startsWith("Worker-Investigate")) return "investigation";
  return stages.find((stage) => stage.agent === value)?.id || null;
}

/** "Worker-Investigate-Payments" -> "Payments squad"; other names stay as they are. */
export function shortAgentName(name) {
  const value = String(name || "");
  const squad = value.match(/^Worker-Investigate-(.+)$/);
  return squad ? `${squad[1]} squad` : value;
}

export function messageMeaning(message) {
  const content = message?.content || {};
  const decision = content.decision || content.output?.decision;
  // A rate-limited model call falls back to the local rules, which face the same limits.
  const rateLimitNote =
    content.rate_limited || content.output?.rate_limited
      ? " The model service was rate limited, so the local rule-based assessment was checked against the same limits."
      : "";
  const utility = Number(content.utility || 0).toFixed(3);
  switch (message?.performative) {
    case "cfp":
      return "The broker asks the available workers to bid with their skill, current workload and cost for this task.";
    case "propose":
      return `${shortAgentName(message.sender)} bids for the task. Its utility score is ${utility}; the highest score wins.`;
    case "accept-proposal":
      return `${shortAgentName(content.worker_id || recipients(message)[0])} wins the task with a utility score of ${utility}.`;
    case "reject-proposal":
      return "This bid is declined because another worker scored higher. The ticket continues with the winner.";
    default:
      break;
  }
  if (decision === "accepted")
    return "The reviewer approved. The next agent continues, and the note is saved with the ticket.";
  if (decision === "rejected") return "The reviewer stopped this run. No further stage will run.";
  if (decision === "request_changes" || decision === "changes_requested")
    return "The reviewer asked the responsible agent to revise its result before the run continues.";
  if (decision === "escalated")
    return `The impact or uncertainty is outside the policy limits, so a person must review this result.${rateLimitNote}`;
  if (decision === "autonomous")
    return `The assessment is confident enough and the risk is low enough, so worker selection may continue.${rateLimitNote}`;
  if (decision === "linked_duplicate")
    return `This report repeats an existing ticket${content.parent_ticket_id ? ` (${content.parent_ticket_id})` : ""}, so it is linked there and this run closes.`;
  if (content.summary) return content.summary;
  if (content.stage === "monitoring")
    return "Monitoring hands its result back to Triage, which closes the feedback loop.";
  if (content.stage) {
    const stage = stageInfo(content.stage);
    const name = stage.name === "QA" ? "QA" : stage.name.toLowerCase();
    return `${stage.agent} shares its ${name} result. ${stage.description}`;
  }
  return message?.summary || "The sender shares a result with the next participant. All messages for a ticket carry the same ticket reference.";
}

/** Merge history and live messages by id, oldest first, keeping at most 500. */
export function mergeMessages(current, incoming) {
  const map = new Map(current.map((item) => [item.message_id, item]));
  incoming.forEach((item) => map.set(item.message_id, item));
  return [...map.values()]
    .sort((a, b) => (a.occurred_at || "").localeCompare(b.occurred_at || ""))
    .slice(-500);
}

/** Map backend stage statuses (and a few older spellings) to the five the dashboard uses. */
function stageStatus(value) {
  const status = String(value || "upcoming");
  if (["completed", "done", "complete"].includes(status)) return "completed";
  if (["current", "active", "running", "waiting"].includes(status)) return "current";
  if (["rejected", "stopped"].includes(status)) return "rejected";
  if (status === "skipped") return "skipped";
  return "upcoming";
}

const SEVERITIES = ["Low", "Medium", "High", "Critical"];

/**
 * Turn any ticket snapshot into one predictable shape. It absorbs small API drift:
 * missing arrays, `waiting_for: "rejected"` (no gate), stages keyed by name or id.
 */
export function normalizeSnapshot(raw) {
  const record = raw && typeof raw === "object" ? raw : {};
  const status = record.status || "running";
  const currentStage = stageIds.includes(record.current_stage) ? record.current_stage : "intake";
  const waitingFor = record.waiting_for && record.waiting_for !== "rejected" ? record.waiting_for : null;
  const given = Array.isArray(record.stages) ? record.stages : [];
  const stageList = stages.map((stage, index) => {
    const found = given.find((item) => (item?.name || item?.id || item?.stage) === stage.id) || {};
    let state = stageStatus(found.status);
    if (!found.status) state = index < stageIds.indexOf(currentStage) ? "completed" : index === stageIds.indexOf(currentStage) ? "current" : "upcoming";
    return { name: stage.id, agent: found.agent || stage.agent, status: state, entered_at: found.entered_at || null };
  });
  let pendingGate = null;
  if (status === "waiting_for_review" && (record.pending_gate || waitingFor)) {
    const pending = record.pending_gate || {};
    const id = pending.gate || waitingFor;
    pendingGate = {
      gate: id,
      stage: pending.stage || gateInfo(id)?.stage || currentStage,
      reason: pending.reason || null,
      question: pending.question || gateInfo(id)?.label || "Human review",
      allowed_intents: Array.isArray(pending.allowed_intents) && pending.allowed_intents.length ? pending.allowed_intents : INTENTS,
      evidence: pending.evidence && typeof pending.evidence === "object" ? pending.evidence : {},
    };
  }
  return {
    ...record,
    ticket_id: record.ticket_id || "unknown",
    title: record.title || "Untitled ticket",
    body: record.body || "",
    severity: SEVERITIES.includes(record.severity) ? record.severity : "Unknown",
    status,
    current_stage: currentStage,
    waiting_for: status === "waiting_for_review" ? waitingFor : null,
    stages: stageList,
    agent_outputs: record.agent_outputs && typeof record.agent_outputs === "object" ? record.agent_outputs : {},
    reviews: Array.isArray(record.reviews) ? record.reviews : [],
    pending_gate: pendingGate,
    follow_up_ticket_ids: Array.isArray(record.follow_up_ticket_ids) ? record.follow_up_ticket_ids : [],
    irreversible_actions: Array.isArray(record.irreversible_actions) ? record.irreversible_actions : [],
    channel: record.channel || "manual",
    duplicate_of: record.duplicate_of || null,
    parent_ticket_id: record.parent_ticket_id || null,
    assignee: record.assignee || null,
  };
}

export function isWaiting(record) {
  return record?.status === "waiting_for_review" && Boolean(record?.waiting_for || record?.pending_gate);
}

/**
 * The agent's question when it could not act on the reviewer's last note (for example a
 * change request without the model). Null once the ticket has moved on.
 */
export function clarificationQuestion(record) {
  const latest = record?.reviews?.at?.(-1);
  if (!isWaiting(record) || latest?.decision !== "clarification_requested") return null;
  const gate = record.pending_gate?.gate || record.waiting_for;
  if (latest.checkpoint && gate && latest.checkpoint !== gate) return null;
  return latest.interpretation?.clarification_question || "Please explain the change you want more precisely.";
}

/** When a ticket entered a stage: the stage's own time, then the ticket's start for intake. */
export function stageEnteredAt(record, stageId) {
  const entry = (record?.stages || []).find((item) => (item?.name || item?.id) === stageId);
  if (entry?.entered_at) return entry.entered_at;
  const output = record?.agent_outputs?.[stageId];
  if (output?.entered_at) return output.entered_at;
  if (stageId === "intake" && record?.created_at) return record.created_at;
  return null;
}

/** The agent working on the ticket now; the winning squad replaces the generic investigator. */
export function currentAgent(record) {
  const stage = record?.current_stage;
  const entry = (record?.stages || []).find((item) => (item?.name || item?.id) === stage);
  if (stage === "investigation" && record?.assignee) return record.assignee;
  return entry?.agent || stageInfo(stage).agent;
}
