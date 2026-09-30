import test from "node:test";
import assert from "node:assert/strict";
import {
  mergeMessages,
  messageMeaning,
  recipients,
  workflow,
} from "./workflow.js";
import { sampleConversation } from "./sampleConversation.js";

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
  const history = [
    { message_id: "a", occurred_at: "2026-09-30T02:00:01Z" },
    live[0],
  ];
  assert.deepEqual(
    mergeMessages(live, history).map((item) => item.message_id),
    ["a", "b", "c"],
  );
  assert.deepEqual(recipients({ receiver: "Worker-QA" }), ["Worker-QA"]);
});
test("the example's winner agrees with the report's utility formula", () => {
  const bids = sampleConversation
    .filter((item) => item.performative === "propose")
    .map((item) => item.content);
  bids.forEach((bid) =>
    assert.ok(
      Math.abs(
        bid.utility -
          (0.5 * bid.skill + 0.3 * (1 - bid.load) + 0.2 * (1 - bid.cost)),
      ) < 1e-10,
    ),
  );
  const best = bids.sort((a, b) => b.utility - a.utility)[0];
  const selected = sampleConversation.find(
    (item) => item.performative === "accept-proposal",
  );
  assert.equal(selected.content.worker_id, best.worker_id);
  assert.ok(Math.abs(best.utility - 0.69) < 1e-10);
});
test("the example covers all nine stages and returns monitoring to triage", () => {
  assert.deepEqual(
    new Set(
      sampleConversation.map((item) => item.content.stage).filter(Boolean),
    ),
    new Set(workflow.map((item) => item.id)),
  );
  assert.equal(sampleConversation.at(-1).sender, "Scout-Monitor");
  assert.deepEqual(recipients(sampleConversation.at(-1)), ["Broker-Triage"]);
});
