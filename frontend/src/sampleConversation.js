// An explicitly illustrative conversation. Bid inputs match the report's worked example.
const messages = [];
function add(sender, receiver, performative, content) {
  const index = messages.length;
  messages.push({
    message_id: `sample-${index}`,
    correlation_id: "TCK-1042",
    occurred_at: new Date(Date.UTC(2026, 8, 30, 2, 0, index * 4)).toISOString(),
    sender,
    receiver,
    performative,
    content: {
      ...(["cfp", "propose", "accept-proposal", "reject-proposal"].includes(
        performative,
      )
        ? { stage: "assignment" }
        : {}),
      ...content,
    },
    policy_context: { tau: 0.7, risk_max: 0.6 },
  });
}
add("Scout-Feedback", ["Broker-Triage"], "inform", {
  stage: "intake",
  summary: "Reports are organized into one incident ticket.",
  output: {
    normalized_title: "Checkout fails during a flash sale",
    source: "Illustrative checkout incident",
  },
});
add("Broker-Triage", ["Security-Policy"], "inform", {
  stage: "triage",
  output: {
    severity: "Critical",
    rule_score: 0.88,
    rationale: "Customers cannot place orders during the sale.",
  },
});
add("Security-Policy", ["Human-Reviewer"], "inform", {
  decision: "escalated",
  risk: 1,
  summary: "Critical impact exceeds the allowed risk of 0.60.",
});
add("Human-Reviewer", ["Broker-Assign"], "inform", {
  decision: "accepted",
  checkpoint: "autonomy_gate",
  note: "Confirm the business impact and investigate urgently.",
});
add(
  "Broker-Assign",
  ["Worker-Plan", "Worker-Investigate", "Worker-Impl"],
  "cfp",
  { task: "Investigate the checkout incident", ticket_id: "TCK-1042" },
);
for (const [worker_id, skill, load, cost] of [
  ["Worker-Plan", 0.9, 0.8, 0.4],
  ["Worker-Investigate", 0.7, 0.2, 0.5],
  ["Worker-Impl", 0.5, 0.1, 0.3],
])
  add(worker_id, ["Broker-Assign"], "propose", {
    worker_id,
    skill,
    load,
    cost,
    utility: 0.5 * skill + 0.3 * (1 - load) + 0.2 * (1 - cost),
  });
add("Broker-Assign", ["Worker-Investigate"], "accept-proposal", {
  worker_id: "Worker-Investigate",
  utility: 0.69,
});
add("Broker-Assign", ["Worker-Plan"], "reject-proposal", {
  worker_id: "Worker-Plan",
  utility: 0.63,
});
add("Broker-Assign", ["Worker-Impl"], "reject-proposal", {
  worker_id: "Worker-Impl",
  utility: 0.66,
});
add("Worker-Investigate", ["Worker-Plan"], "inform", {
  stage: "investigation",
  output: {
    status: "hypotheses_only",
    ranked_hypotheses: [
      {
        hypothesis: "Payment database connection saturation",
        evidence: "Illustrative incident evidence",
        confidence: 0.42,
      },
    ],
    root_cause_confirmed: false,
  },
});
add("Worker-Plan", ["Worker-Impl"], "inform", {
  stage: "planning",
  output: {
    status: "plan_drafted",
    subtasks: [
      "Reproduce checkout failure",
      "Check database connections",
      "Prepare a scoped fix",
    ],
    acceptance_criteria: ["Checkout remains available under peak load"],
  },
});
add("Worker-Impl", ["Worker-QA"], "inform", {
  stage: "implementation",
  output: {
    status: "change_request_drafted",
    code_change_generated: false,
    repository_access: false,
  },
});
add("Worker-QA", ["Human-Reviewer"], "inform", {
  stage: "qa",
  output: {
    tests_executed: 0,
    pass_fail: "undetermined",
    recommended_checks: [
      "Reproduce the failure",
      "Run a load test",
      "Check for regressions",
    ],
  },
});
add("Human-Reviewer", ["Worker-Deploy"], "inform", {
  decision: "accepted",
  checkpoint: "pr_merge",
  note: "Accept the example verification proposal for the classroom walkthrough.",
});
add("Worker-Deploy", ["Human-Reviewer"], "inform", {
  stage: "deployment",
  output: {
    status: "canary_proposal_only",
    rollout_percentage: 5,
    full_release_executed: false,
  },
});
add("Human-Reviewer", ["Scout-Monitor"], "inform", {
  decision: "accepted",
  checkpoint: "release_signoff",
  note: "Accept the simulated release proposal.",
});
add("Scout-Monitor", ["Broker-Triage"], "inform", {
  stage: "monitoring",
  output: {
    status: "awaiting_telemetry",
    feedback_loop_target: "Broker-Triage",
    follow_up_ticket_created: false,
  },
});
export const sampleConversation = messages;
