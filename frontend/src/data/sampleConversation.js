// An explicitly illustrative conversation: the report's TCK-1042 flash-sale story.
// Bid inputs match the report's worked example; policy numbers come from DEFAULT_POLICY.
// `time_label` gives the story clock (T+mm:ss) that the replay shows.
import { DEFAULT_POLICY } from "../lib/policy.js";
import { formatNumber } from "../lib/format.js";

const policy = DEFAULT_POLICY;
const policyContext = { tau: policy.tau, risk_max: policy.risk_max };
const messages = [];

// The story starts on 10 Oct 2026 at 20:03 WIB (13:03 UTC); each message's clock time
// matches its T+ label, so the timeline and the animation agree.
const START = Date.UTC(2026, 9, 10, 13, 3, 0);

function add(sender, receiver, performative, content, timeLabel) {
  const index = messages.length;
  const [minutes, seconds] = timeLabel.slice(2).split(":").map(Number);
  messages.push({
    message_id: `sample-${index}`,
    correlation_id: "TCK-1042",
    occurred_at: new Date(START + (minutes * 60 + seconds) * 1000).toISOString(),
    sender,
    receiver,
    performative,
    content: {
      ...(["cfp", "propose", "accept-proposal", "reject-proposal"].includes(performative) ? { stage: "assignment" } : {}),
      ...content,
      time_label: timeLabel,
    },
    policy_context: policyContext,
  });
}

add("Scout-Feedback", ["Broker-Triage"], "inform", {
  stage: "intake",
  summary: "2,143 crash reports from the flash sale become one ticket; contact details are masked.",
  output: {
    normalized_title: "Checkout crashes when paying during the flash sale",
    source: "Crash reporter + app reviews (illustrative)",
    grouped_reports: 2143,
    linked_duplicates: 2142,
    app_version: "4.18.2",
    platform: "Android",
  },
}, "T+00:00");
add("Broker-Triage", ["Security-Policy"], "inform", {
  stage: "triage",
  summary: "Severity Critical (rule score 0.88). Closest older ticket TCK-0987 is only 0.62 similar, so this is a new issue.",
  output: {
    severity: "Critical",
    rule_score: 0.88,
    rationale: "Customers are charged but get no order during the sale.",
    duplicate: {
      band: "new",
      best_match: { ticket_id: "TCK-0987", cosine: 0.62 },
      note: "Related checkout bug, but a different load context",
    },
  },
}, "T+00:04");
add("Security-Policy", ["Human-Reviewer"], "inform", {
  decision: "escalated",
  checkpoint: "autonomy_gate",
  risk: policy.risk_by_class.Critical,
  summary: `Critical impact has risk ${formatNumber(policy.risk_by_class.Critical, 2)}, above the allowed ${formatNumber(policy.risk_max, 2)}, so a person must confirm.`,
}, "T+00:05");
add("Human-Reviewer", ["Broker-Assign"], "inform", {
  decision: "accepted",
  checkpoint: "autonomy_gate",
  note: "Confirm the business impact and investigate urgently.",
}, "T+00:20");
add("Broker-Assign", ["Worker-Plan", "Worker-Investigate", "Worker-Impl"], "cfp", {
  task: "Investigate the checkout incident",
  ticket_id: "TCK-1042",
}, "T+00:22");
for (const [worker_id, skill, load, cost, time] of [
  ["Worker-Plan", 0.9, 0.8, 0.4, "T+00:23"],
  ["Worker-Investigate", 0.7, 0.2, 0.5, "T+00:23"],
  ["Worker-Impl", 0.5, 0.1, 0.3, "T+00:24"],
])
  add(worker_id, ["Broker-Assign"], "propose", {
    worker_id,
    skill,
    load,
    cost,
    utility: 0.5 * skill + 0.3 * (1 - load) + 0.2 * (1 - cost),
  }, time);
add("Broker-Assign", ["Worker-Investigate"], "accept-proposal", { worker_id: "Worker-Investigate", utility: 0.69 }, "T+00:25");
add("Broker-Assign", ["Worker-Plan"], "reject-proposal", { worker_id: "Worker-Plan", utility: 0.63 }, "T+00:25");
add("Broker-Assign", ["Worker-Impl"], "reject-proposal", { worker_id: "Worker-Impl", utility: 0.66 }, "T+00:25");
add("Worker-Investigate", ["Scout-Log"], "inform", {
  stage: "investigation",
  summary: "Scout-Log is sent to the six data nodes with a signed bundle to read the incident window locally.",
  output: { task: "Aggregate checkout errors and latency for 20:00–20:30 on every node", nodes: 6 },
}, "T+00:30");
add("Scout-Log", ["Worker-Investigate"], "inform", {
  stage: "investigation",
  summary: "Scout-Log returns only aggregates: 84 MB moved in about 27 s, while 8,190 MB of raw logs stayed on the nodes.",
  output: { nodes: 6, mb_sent: 72, mb_returned: 12, total_mb: 84, elapsed_s: 27 },
}, "T+00:57");
add("Worker-Investigate", ["Worker-Plan"], "inform", {
  stage: "investigation",
  summary: "Top suspect: payment-db connection pool exhaustion (illustrative evidence).",
  output: {
    status: "hypotheses_only",
    ranked_hypotheses: [
      { hypothesis: "Payment database connection saturation", evidence: "Illustrative incident evidence", confidence: 0.42 },
    ],
    root_cause_confirmed: false,
  },
}, "T+01:10");
add("Worker-Plan", ["Worker-Impl"], "inform", {
  stage: "planning",
  output: {
    status: "plan_drafted",
    subtasks: ["Reproduce checkout failure", "Check database connections", "Prepare a scoped fix"],
    acceptance_criteria: ["Checkout remains available under peak load"],
  },
}, "T+01:40");
add("Worker-Impl", ["Worker-QA"], "inform", {
  stage: "implementation",
  output: { status: "change_request_drafted", code_change_generated: false, repository_access: false },
}, "T+02:20");
add("Worker-QA", ["Human-Reviewer"], "inform", {
  stage: "qa",
  output: {
    tests_executed: 0,
    pass_fail: "undetermined",
    recommended_checks: ["Reproduce the failure", "Run a load test", "Check for regressions"],
  },
}, "T+03:00");
add("Human-Reviewer", ["Worker-Deploy"], "inform", {
  decision: "accepted",
  checkpoint: "pr_merge",
  note: "Accept the example verification proposal for the classroom walkthrough.",
}, "T+03:30");
add("Worker-Deploy", ["Human-Reviewer"], "inform", {
  stage: "deployment",
  summary: `Release risk 0.28 is within ${formatNumber(policy.canary.risk_max, 2)}, so the ${policy.canary.percent}% canary may start on its own; the full release waits for a person.`,
  output: { status: "canary_proposal_only", risk_score: 0.28, rollout_percentage: policy.canary.percent, full_release_executed: false },
}, "T+03:50");
add("Human-Reviewer", ["Scout-Monitor"], "inform", {
  decision: "accepted",
  checkpoint: "release_signoff",
  note: "Accept the simulated release proposal.",
}, "T+04:10");
add("Scout-Monitor", ["Broker-Triage"], "inform", {
  stage: "monitoring",
  summary: `No SLO breach in ${policy.canary.observe_minutes} minutes after the release, so the baseline is updated and the result returns to Triage.`,
  output: { status: "healthy", feedback_loop_target: "Broker-Triage", baseline_updated: true, follow_up_ticket_created: false },
}, "T+04:30");

export const sampleConversation = messages;

/** Frames shown before and after the messages in the Overview replay. */
export const sampleIntro = {
  caption: "2,143 crash reports arrive in 4 minutes during the 10.10 flash sale. Scout-Feedback turns them into one ticket.",
  timeLabel: "T−04:00",
};
export const sampleOutro = {
  caption: `No SLO breach in ${policy.canary.observe_minutes} minutes → the baseline is updated. The loop returns to Triage, ready for the next report.`,
  timeLabel: "T+04:30",
};
