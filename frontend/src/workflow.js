export const workflow = [
  {
    id: "intake",
    label: "Receive issue",
    agent: "Scout-Feedback",
    description: "Organize the report and protect personal information.",
  },
  {
    id: "triage",
    label: "Assess impact",
    agent: "Broker-Triage",
    description: "Explain the urgency and ask for review when risk is high.",
  },
  {
    id: "assignment",
    label: "Choose a worker",
    agent: "Broker-Assign",
    description: "Compare bids using skill, workload, and cost.",
  },
  {
    id: "investigation",
    label: "Investigate",
    agent: "Worker-Investigate",
    description: "Suggest likely causes and evidence to collect.",
  },
  {
    id: "planning",
    label: "Plan the fix",
    agent: "Worker-Plan",
    description: "Define tasks and what a successful fix should do.",
  },
  {
    id: "implementation",
    label: "Prepare a change",
    agent: "Worker-Impl",
    description: "Draft the change request for the development team.",
  },
  {
    id: "qa",
    label: "Check quality",
    agent: "Worker-QA",
    description: "Prepare verification checks, then request merge review.",
  },
  {
    id: "deployment",
    label: "Review release",
    agent: "Worker-Deploy",
    description: "Propose a small rollout and request release approval.",
  },
  {
    id: "monitoring",
    label: "Monitor & learn",
    agent: "Scout-Monitor",
    description: "Return monitoring signals to the impact assessment agent.",
  },
];
export const stageInfo = (id) =>
  workflow.find((stage) => stage.id === id) || {
    label: id || "Workflow",
    agent: "Orchestrator",
  };
export const checkpointLabel = (id) =>
  ({
    autonomy_gate: "Confirm the impact assessment",
    pr_merge: "Review the proposed change",
    release_signoff: "Approve the release proposal",
  })[id] || "Human review";
export const statusLabel = (id) =>
  ({
    running: "In progress",
    waiting_for_review: "Needs your review",
    completed: "Prototype completed",
    rejected: "Stopped by reviewer",
  })[id] || id;
export const localTime = (value) => {
  const date = new Date(value);
  return !value || Number.isNaN(date.getTime())
    ? "Time unavailable"
    : date.toLocaleTimeString("en-GB", {
        timeZone: "Asia/Jakarta",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
};
export const recipients = (message) => {
  const value = message?.receiver || message?.receivers || [];
  return Array.isArray(value) ? value : [value];
};
export const messageLabel = (value) =>
  ({
    cfp: "Request worker bids",
    propose: "Submit a bid",
    "accept-proposal": "Select a worker",
    "reject-proposal": "Close another bid",
    inform: "Share a result",
    refuse: "Decline the task",
    failure: "Report a problem",
  })[value] || value;
export function messageMeaning(message) {
  const content = message?.content || {};
  const decision = content.decision || content.output?.decision;
  if (message?.performative === "cfp")
    return "The coordinator asks available workers to offer their skills, workload, and cost for this task.";
  if (message?.performative === "propose")
    return `This worker offers to help. Its selection score is ${Number(content.utility || 0).toFixed(3)}; a higher score is preferred.`;
  if (message?.performative === "accept-proposal")
    return `${content.worker_id || recipients(message)[0]} wins the task with a selection score of ${Number(content.utility || 0).toFixed(3)}.`;
  if (message?.performative === "reject-proposal")
    return "This bid is closed because another worker received a higher selection score. The ticket continues.";
  if (decision === "accepted")
    return "The reviewer accepted the proposal. The next agent can continue with the recorded feedback.";
  if (decision === "rejected")
    return "The reviewer stopped this run. No further stage will execute.";
  if (decision === "request_changes")
    return "The reviewer asks the responsible agent to revise its result before continuing.";
  if (decision === "escalated")
    return "The impact or uncertainty exceeds the policy limits. A person must review this result.";
  if (decision === "autonomous")
    return "The assessment meets the confidence and risk limits, so worker selection may continue.";
  if (content.stage === "monitoring")
    return "The monitoring agent returns its result to triage, closing the feedback loop. Live telemetry is not connected in this prototype.";
  if (content.stage)
    return `${stageInfo(content.stage).agent} shares its ${stageInfo(content.stage).label.toLowerCase()} result. ${stageInfo(content.stage).description}`;
  return (
    content.summary ||
    message?.summary ||
    "The sender shares a result with the next participant. All messages for this ticket use the same ticket reference."
  );
}
export function mergeMessages(current, incoming) {
  const map = new Map(current.map((item) => [item.message_id, item]));
  incoming.forEach((item) => map.set(item.message_id, item));
  return [...map.values()]
    .sort((a, b) => (a.occurred_at || "").localeCompare(b.occurred_at || ""))
    .slice(-500);
}
