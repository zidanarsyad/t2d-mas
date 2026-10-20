import test from "node:test";
import assert from "node:assert/strict";
import {
  clarificationQuestion,
  currentAgent,
  gates,
  intentEffects,
  isAgentName,
  mergeMessages,
  messageMeaning,
  normalizeSnapshot,
  performativeLabel,
  recipients,
  stageEnteredAt,
  stageIds,
  stageOfAgent,
  stateLabel,
  statusLabel,
  workflow,
} from "./workflow.js";
import { canaryAllowed, DEFAULT_POLICY } from "./policy.js";
import { sampleConversation } from "../data/sampleConversation.js";

test("recorded policy handoffs explain decisions nested in agent output", () => {
  const message = {
    performative: "inform",
    content: { stage: "triage", output: { decision: "escalated" } },
  };
  assert.match(messageMeaning(message), /person must review/i);
  message.content.output.decision = "autonomous";
  assert.match(messageMeaning(message), /worker selection may continue/i);
});

test("reconnecting merges history and live messages in chronological order without duplicates", () => {
  const live = [
    { message_id: "b", occurred_at: "2026-09-30T02:00:02Z" },
    { message_id: "c", occurred_at: "2026-09-30T02:00:03Z" },
  ];
  const history = [{ message_id: "a", occurred_at: "2026-09-30T02:00:01Z" }, live[0]];
  assert.deepEqual(
    mergeMessages(live, history).map((item) => item.message_id),
    ["a", "b", "c"],
  );
  assert.deepEqual(recipients({ receiver: "Worker-QA" }), ["Worker-QA"]);
});

test("the example's winner agrees with the report's utility formula", () => {
  const bids = sampleConversation.filter((item) => item.performative === "propose").map((item) => item.content);
  bids.forEach((bid) =>
    assert.ok(Math.abs(bid.utility - (0.5 * bid.skill + 0.3 * (1 - bid.load) + 0.2 * (1 - bid.cost))) < 1e-10),
  );
  const best = bids.sort((a, b) => b.utility - a.utility)[0];
  const selected = sampleConversation.find((item) => item.performative === "accept-proposal");
  assert.equal(selected.content.worker_id, best.worker_id);
  assert.ok(Math.abs(best.utility - 0.69) < 1e-10);
});

test("the example covers all nine stages and returns monitoring to triage", () => {
  assert.deepEqual(
    new Set(sampleConversation.map((item) => item.content.stage).filter(Boolean)),
    new Set(workflow.map((item) => item.id)),
  );
  assert.equal(sampleConversation.at(-1).sender, "Scout-Monitor");
  assert.deepEqual(recipients(sampleConversation.at(-1)), ["Broker-Triage"]);
});

test("the nine stage ids follow the backend order", () => {
  assert.deepEqual(stageIds, ["intake", "triage", "assignment", "investigation", "planning", "implementation", "qa", "deployment", "monitoring"]);
});

test("every gate belongs to a known stage and has review effects", () => {
  assert.equal(gates.length, 6);
  gates.forEach((gate) => {
    assert.ok(stageIds.includes(gate.stage), gate.id);
    assert.ok(intentEffects[gate.id], gate.id);
  });
  assert.deepEqual(DEFAULT_POLICY.gates.map((gate) => gate.gate), gates.map((gate) => gate.id));
});

test("labels cover every status, state and performative", () => {
  ["running", "waiting_for_review", "completed", "rejected", "duplicate"].forEach((status) =>
    assert.notEqual(statusLabel(status), status.replaceAll("_", " ")),
  );
  ["done", "active", "waiting", "revising", "stopped", "upcoming", "skipped"].forEach((state) => assert.ok(stateLabel[state]));
  ["cfp", "propose", "accept-proposal", "reject-proposal", "inform", "refuse", "failure"].forEach((value) =>
    assert.notEqual(performativeLabel(value), value),
  );
});

test("normalizeSnapshot fills defaults and treats waiting_for 'rejected' as no gate", () => {
  const record = normalizeSnapshot({ ticket_id: "T-1", status: "rejected", waiting_for: "rejected", current_stage: "qa" });
  assert.equal(record.waiting_for, null);
  assert.equal(record.pending_gate, null);
  assert.equal(record.severity, "Unknown");
  assert.equal(record.stages.length, 9);
  assert.deepEqual(record.reviews, []);
  const waiting = normalizeSnapshot({ ticket_id: "T-2", status: "waiting_for_review", waiting_for: "pr_merge", current_stage: "qa" });
  assert.equal(waiting.pending_gate.gate, "pr_merge");
  assert.equal(waiting.pending_gate.stage, "qa");
  assert.deepEqual(waiting.pending_gate.allowed_intents, ["accept", "request_changes", "reject"]);
});

test("stageEnteredAt prefers the stage's own time, then the ticket start for intake", () => {
  const record = {
    created_at: "2026-10-20T01:00:00Z",
    stages: [{ name: "intake" }, { name: "triage", entered_at: "2026-10-20T01:00:05Z" }],
    agent_outputs: { planning: { entered_at: "2026-10-20T01:10:00Z" } },
  };
  assert.equal(stageEnteredAt(record, "triage"), "2026-10-20T01:00:05Z");
  assert.equal(stageEnteredAt(record, "intake"), "2026-10-20T01:00:00Z");
  assert.equal(stageEnteredAt(record, "planning"), "2026-10-20T01:10:00Z");
  assert.equal(stageEnteredAt(record, "qa"), null);
});

test("agent names map to stages, and a reviewer's name counts as a person", () => {
  assert.equal(stageOfAgent("Worker-Investigate-Payments"), "investigation");
  assert.equal(stageOfAgent("Scout-Monitor"), "monitoring");
  assert.equal(isAgentName("Project reviewer"), false);
  assert.equal(currentAgent({ current_stage: "investigation", assignee: "Worker-Investigate-Mobile", stages: [] }), "Worker-Investigate-Mobile");
});

test("the enriched story moves 84 MB = 6 × (12 + 2) and its canary may start alone", () => {
  const trip = sampleConversation.find((item) => item.sender === "Scout-Log").content.output;
  const { agent_bundle_mb: bundle, result_mb: result } = DEFAULT_POLICY.migration;
  assert.equal(trip.total_mb, trip.nodes * (bundle + result));
  assert.equal(trip.mb_sent, trip.nodes * bundle);
  const deployment = sampleConversation.find((item) => item.content.stage === "deployment").content.output;
  assert.equal(deployment.risk_score, 0.28);
  assert.equal(canaryAllowed(deployment.risk_score), true);
});

test("clarificationQuestion shows the agent's question only while the gate still waits", () => {
  const review = { checkpoint: "autonomy_gate", decision: "clarification_requested", interpretation: { clarification_question: "Which severity?" } };
  const waiting = { status: "waiting_for_review", waiting_for: "autonomy_gate", pending_gate: { gate: "autonomy_gate" }, reviews: [review] };
  assert.equal(clarificationQuestion(waiting), "Which severity?");
  assert.equal(clarificationQuestion({ ...waiting, status: "running", waiting_for: null }), null);
  assert.equal(clarificationQuestion({ ...waiting, reviews: [review, { checkpoint: "autonomy_gate", decision: "accepted" }] }), null);
});
