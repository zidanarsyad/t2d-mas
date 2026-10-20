import test from "node:test";
import assert from "node:assert/strict";
import { entriesFromAudit, entriesFromMessages } from "./trace.js";
import { sampleConversation } from "../data/sampleConversation.js";

test("messages and audit events become the same entry shape", () => {
  const fromMessages = entriesFromMessages(sampleConversation);
  const fromAudit = entriesFromAudit([
    { occurred_at: "2026-10-20T01:00:00Z", agent: "Broker-Triage", action: "agent_message", decision: "publish_authorized", performative: "inform", receivers: ["Broker-Assign"], output: { stage: "triage" } },
    { occurred_at: "2026-10-20T01:00:00Z", agent: "Broker-Triage", action: "agent_message", decision: "published", performative: "inform", receivers: ["Broker-Assign"], output: { stage: "triage" }, message_id: "m-1" },
    { occurred_at: "2026-10-20T01:00:01Z", agent: "Security-Policy", action: "policy_gate", decision: "escalated", checkpoint: "autonomy_gate", confidence: 0.88, tau: 0.7, risk: 1, risk_max: 0.6 },
    { occurred_at: "2026-10-20T01:02:00Z", agent: "Orchestrator", action: "human_approval", decision: "approved", approver: "Dina", note: "Looks right", checkpoint: "autonomy_gate" },
    { occurred_at: "2026-10-20T01:03:00Z", agent: "Broker-Assign", action: "agent_output", decision: "completed", stage: "assignment", output: { summary: "Assigned to Payments" } },
  ]);
  const keys = Object.keys(fromMessages[0]).sort();
  fromAudit.forEach((item) => assert.deepEqual(Object.keys(item).sort(), keys));
  assert.equal(fromAudit.length, 4, "the authorized twin of a message is skipped");
  assert.deepEqual(fromAudit.map((item) => item.kind), ["message", "gate", "decision", "output"]);
  assert.match(fromAudit[1].detail, /0\.88/);
  assert.equal(fromAudit[2].actor, "Dina");
});

test("the sample story has decisions, gates and contract-net messages", () => {
  const entries = entriesFromMessages(sampleConversation);
  assert.equal(entries.length, sampleConversation.length);
  assert.ok(entries.some((item) => item.kind === "decision"));
  assert.ok(entries.some((item) => item.kind === "gate"));
  assert.ok(entries.filter((item) => item.stage === "assignment").length >= 6);
});
