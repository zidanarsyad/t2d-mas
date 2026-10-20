import test from "node:test";
import assert from "node:assert/strict";
import {
  agentAnchor,
  anchorPoint,
  describeFrame,
  enqueueFrames,
  envelopeLine,
  frameFromSnapshot,
  framesFromMessages,
  layoutFlow,
  replayFrames,
} from "./flow.js";
import { stageIds } from "./workflow.js";
import { sampleConversation, sampleIntro, sampleOutro } from "../data/sampleConversation.js";

const RANK = { upcoming: 0, skipped: 0, active: 1, waiting: 1, revising: 1, done: 2, stopped: 3 };
const replay = replayFrames(sampleConversation, { intro: sampleIntro, outro: sampleOutro });

test("every envelope endpoint resolves to a drawn anchor", () => {
  const layout = layoutFlow();
  replay.forEach((frame) =>
    frame.envelopes.forEach((envelope) => {
      assert.ok(layout.nodes[envelope.from] || layout.anchors[envelope.from], `${frame.id} from ${envelope.from}`);
      assert.ok(layout.nodes[envelope.to] || layout.anchors[envelope.to], `${frame.id} to ${envelope.to}`);
      const line = envelopeLine(envelope, layout);
      assert.ok([line.x1, line.y1, line.x2, line.y2].every(Number.isFinite));
    }),
  );
});

test("stage states never go backwards during the replay", () => {
  stageIds.forEach((id) => {
    let previous = 0;
    replay.forEach((frame) => {
      const rank = RANK[frame.stages[id]];
      assert.ok(rank >= previous, `${id} went from ${previous} to ${frame.stages[id]} at ${frame.id}`);
      previous = rank;
    });
  });
});

test("the replay tells the whole TCK-1042 story", () => {
  assert.ok(replay.length >= 20 && replay.length <= 26, `frames: ${replay.length}`);
  const total = replay.reduce((sum, frame) => sum + frame.durationMs, 0);
  assert.ok(total > 20000 && total < 32000, `duration ${total}`);
  assert.equal(replay.at(-1).loop, true);
  assert.ok(replay.at(-1).stages.monitoring === "done");
  assert.ok(replay.some((frame) => frame.gate?.state === "waiting"));
  assert.ok(replay.some((frame) => frame.bids.some((bid) => bid.winner)));
  assert.ok(replay.some((frame) => frame.badges.some((badge) => badge.text === "84 MB moved")));
});

test("a reviewer's name maps to the human anchor and squads get chips during the auction", () => {
  assert.equal(agentAnchor("Project reviewer"), "human");
  assert.equal(agentAnchor("Human-Reviewer"), "human");
  assert.equal(agentAnchor("Security-Policy"), "security");
  assert.equal(agentAnchor("Worker-Investigate-Payments"), "investigation");
  assert.equal(agentAnchor("Worker-Investigate-Payments", { contractNet: true }), "squad-0");
  const [frame] = framesFromMessages([{ message_id: "x", sender: "Project reviewer", receiver: ["Orchestrator"], performative: "inform", content: { decision: "rejected", checkpoint: "pr_merge" } }]);
  assert.equal(frame.envelopes[0].from, "human");
  assert.equal(frame.stages.qa, "stopped");
});

test("frameFromSnapshot covers waiting, rejected, completed and duplicate tickets", () => {
  const base = { ticket_id: "T-9", current_stage: "triage", stages: [{ name: "intake", status: "completed" }, { name: "triage", status: "current" }] };
  const waiting = frameFromSnapshot({ ...base, status: "waiting_for_review", waiting_for: "autonomy_gate" });
  assert.equal(waiting.stages.triage, "waiting");
  assert.equal(waiting.gate.id, "autonomy_gate");
  const rejected = frameFromSnapshot({ ...base, status: "rejected", waiting_for: "rejected", stages: [{ name: "intake", status: "completed" }, { name: "triage", status: "rejected" }], reviews: [{ checkpoint: "autonomy_gate" }] });
  assert.equal(rejected.stages.triage, "stopped");
  assert.equal(rejected.gate.state, "stopped");
  const completed = frameFromSnapshot({ ...base, status: "completed", current_stage: "monitoring" });
  assert.ok(stageIds.every((id) => completed.stages[id] === "done"));
  assert.equal(completed.loop, true);
  const duplicate = frameFromSnapshot({ ...base, status: "duplicate", duplicate_of: "TCK-0001" });
  assert.equal(duplicate.stages.assignment, "skipped");
  assert.ok(duplicate.badges.some((badge) => badge.text === "Duplicate of TCK-0001"));
});

test("the wide layout stays inside its viewBox", () => {
  const layout = layoutFlow();
  [...Object.values(layout.nodes), ...Object.values(layout.anchors)].forEach((point) => {
    assert.ok(point.x - 20 >= 0 && point.x + 20 <= layout.width, `x ${point.x}`);
    assert.ok(point.y - 16 >= 0 && point.y + 16 <= layout.height, `y ${point.y}`);
  });
  assert.deepEqual(anchorPoint("unknown-anchor", layout), layout.anchors.orchestrator);
});

test("enqueueFrames keeps only the newest frames", () => {
  const frames = Array.from({ length: 12 }, (_, index) => ({ id: `f${index}` }));
  const queue = enqueueFrames([{ id: "old" }], frames, 8);
  assert.equal(queue.length, 8);
  assert.equal(queue.at(-1).id, "f11");
  assert.ok(!queue.some((frame) => frame.id === "old"));
});

test("describeFrame reads the gate and the stage states", () => {
  const text = describeFrame(replay.find((frame) => frame.gate?.state === "waiting"));
  assert.match(text, /Human gate/);
  assert.match(text, /Triage: waiting for a human/);
});

test("live frames show the WIB clock instead of T+ offsets", () => {
  const message = { message_id: "a", occurred_at: "2026-10-20T05:00:00Z", sender: "Scout-Feedback", receiver: ["Broker-Triage"], performative: "inform", content: { stage: "intake" } };
  assert.equal(framesFromMessages([message])[0].timeLabel, "T+00:00");
  assert.equal(framesFromMessages([message], { clock: true })[0].timeLabel, "12:00:00 WIB");
});

test("a snapshot says whether its current stage has run yet", () => {
  const base = { ticket_id: "T-5", status: "running", current_stage: "intake", stages: [{ name: "intake", status: "current" }] };
  assert.match(frameFromSnapshot({ ...base, agent_outputs: { intake: { summary: "done" } } }).caption, /has shared its result/);
  assert.match(frameFromSnapshot({ ...base, current_stage: "triage", agent_outputs: {} }).caption, /^Up next: Triage/);
  const asked = frameFromSnapshot({ ...base, status: "waiting_for_review", current_stage: "triage", waiting_for: "autonomy_gate", reviews: [{ checkpoint: "autonomy_gate", decision: "clarification_requested", interpretation: { clarification_question: "Name the severity." } }] });
  assert.match(asked.caption, /clearer note: Name the severity\./);
});
