// The animated pipeline as data. A "frame" is one picture of the flow:
//   { id, stages: {intake: "done", ...}, marker: {stage, label}, envelopes: [...],
//     gate: {id, stage, state} | null, loop, badges, bids, caption, timeLabel, durationMs }
// Frames come from ACL messages (replay and live) or from a ticket snapshot.
import {
  clarificationQuestion,
  defaultGateForStage,
  gateInfo,
  isAgentName,
  messageMeaning,
  normalizeSnapshot,
  recipients,
  shortAgentName,
  stageIds,
  stageInfo,
  stageOfAgent,
  stages,
  stateLabel,
  statusLabel,
} from "./workflow.js";
import { DEFAULT_POLICY, duplicateBand, gateLabel } from "./policy.js";
import { formatBytes, formatNumber, formatOffset, formatTime, toDate } from "./format.js";

const CONTRACT_NET = new Set(["cfp", "propose", "accept-proposal", "reject-proposal"]);
const SQUADS = ["Payments", "Mobile", "Platform"];

/** Node and anchor positions in SVG units. Only the wide layout is used; small screens scroll. */
export function layoutFlow() {
  const rowY = 172;
  const nodes = Object.fromEntries(stages.map((stage, index) => [stage.id, { x: 60 + index * 110, y: rowY }]));
  return {
    width: 1000,
    height: 340,
    rowY,
    laneY: 112, // envelopes between two stages travel along this lane, above the nodes
    markerY: 136,
    nodeRadius: 22,
    nodes,
    anchors: {
      channels: { x: 60, y: 34, label: "Users & channels" },
      security: { x: 170, y: 34, label: "Security-Policy" },
      human: { x: 555, y: 34, label: "Human reviewer" },
      orchestrator: { x: 940, y: 34, label: "Orchestrator" },
      scoutLog: { x: 390, y: 268, label: "Scout-Log (mobile)" },
      "squad-0": { x: 300, y: 84, label: "Payments" },
      "squad-1": { x: 400, y: 84, label: "Mobile app" },
      "squad-2": { x: 500, y: 84, label: "Platform" },
    },
    // The feedback loop runs under the row, from Monitoring back to Triage.
    loopPath: `M ${nodes.monitoring.x} ${rowY + 24} C ${nodes.monitoring.x} 335, ${nodes.triage.x} 335, ${nodes.triage.x} ${rowY + 24}`,
    loopLabel: { x: (nodes.monitoring.x + nodes.triage.x) / 2, y: 322 },
  };
}

/** Which anchor an agent (or a person) is drawn at. Squads get their own chips during the auction. */
export function agentAnchor(name, { contractNet = false } = {}) {
  const value = String(name || "");
  if (!value) return "orchestrator";
  if (value === "channels" || /^(user|customer|channel)/i.test(value)) return "channels";
  if (value.startsWith("Security-")) return "security";
  if (value.startsWith("Human-") || !isAgentName(value)) return "human";
  if (value === "Orchestrator") return "orchestrator";
  if (value.startsWith("Scout-Log")) return "scoutLog";
  const squad = value.match(/^Worker-Investigate-(.+)$/);
  if (squad && contractNet) {
    const known = SQUADS.findIndex((name) => squad[1].toLowerCase().startsWith(name.toLowerCase()));
    const index = known >= 0 ? known : [...squad[1]].reduce((sum, letter) => sum + letter.charCodeAt(0), 0) % 3;
    return `squad-${index}`;
  }
  return stageOfAgent(value) || "orchestrator";
}

export function anchorPoint(id, layout = layoutFlow()) {
  return layout.nodes[id] || layout.anchors[id] || layout.anchors.orchestrator;
}

/** Start and end points of an envelope. Stage-to-stage mail uses the lane above the row. */
export function envelopeLine(envelope, layout = layoutFlow()) {
  const from = anchorPoint(envelope.from, layout);
  const to = anchorPoint(envelope.to, layout);
  if (layout.nodes[envelope.from] && layout.nodes[envelope.to]) {
    return { x1: from.x, y1: layout.laneY, x2: to.x, y2: layout.laneY };
  }
  // Leave the sender's edge and stop short of the receiver, so the envelope covers neither
  // the receiver's label nor the ticket marker that sits just above a stage.
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  // Anchors carry their label underneath, so mail to or from them keeps a wider berth.
  const start = Math.min(layout.nodes[envelope.from] ? 28 : 44, length / 3);
  const end = Math.min(layout.nodes[envelope.to] ? 60 : 46, length / 3);
  return {
    x1: Number((from.x + (dx / length) * start).toFixed(1)),
    y1: Number((from.y + (dy / length) * start).toFixed(1)),
    x2: Number((to.x - (dx / length) * end).toFixed(1)),
    y2: Number((to.y - (dy / length) * end).toFixed(1)),
  };
}

// Rank of each state; a stage's rank never decreases from one frame to the next.
const RANK = { upcoming: 0, skipped: 0, active: 1, waiting: 1, revising: 1, done: 2, stopped: 3 };

function setState(states, id, next) {
  if (!id || !(id in states)) return;
  const current = states[id];
  if (current === "stopped") return;
  if (RANK[next] < RANK[current]) return;
  states[id] = next;
}

function completeBefore(states, id) {
  const end = stageIds.indexOf(id);
  stageIds.slice(0, Math.max(0, end)).forEach((stage) => {
    if (states[stage] !== "skipped") setState(states, stage, "done");
  });
}

const blankStates = () => Object.fromEntries(stageIds.map((id) => [id, "upcoming"]));

/** "Worker-Investigate-Payments" -> "Payments squad", "Worker-Investigate" -> "Investigate". */
const workerBadge = (name) => shortAgentName(name).replace(/^Worker-/, "");

/** Badges a stage result earns (duplicate, winner, bytes moved, release risk). */
function badgesFromOutput(stage, output, policy) {
  const badges = [];
  if (!output || typeof output !== "object") return badges;
  if (stage === "intake" && output.grouped_reports) {
    badges.push({ at: "intake", text: `${formatNumber(output.grouped_reports)} reports → 1 ticket`, tone: "info" });
  }
  if (stage === "triage" && output.duplicate) {
    const match = output.duplicate.best_match || {};
    const cosine = Number(match.cosine ?? output.duplicate.score);
    const band = output.duplicate.band || duplicateBand(cosine, policy);
    // Badges sit side by side under the nodes, so their texts stay short.
    const text =
      band === "auto_link"
        ? `Duplicate of ${match.ticket_id || "older ticket"}`
        : band === "review"
          ? `Maybe duplicate (${formatNumber(cosine, 2)})`
          : `New issue${Number.isFinite(cosine) ? ` (${formatNumber(cosine, 2)})` : ""}`;
    badges.push({ at: "triage", text, tone: band === "new" ? "info" : "warn" });
  }
  if (stage === "assignment" && output.winner) {
    badges.push({ at: "assignment", text: `${workerBadge(output.winner)} · ${formatNumber(output.utility, 2)}`, tone: "accent" });
  }
  if (stage === "investigation") {
    if (output.total_mb) badges.push({ at: "scoutLog", text: `${formatNumber(output.total_mb)} MB moved`, tone: "accent" });
    else if (Number.isFinite(Number(output.bytes_moved))) badges.push({ at: "scoutLog", text: `${formatBytes(output.bytes_moved)} moved`, tone: "accent" });
  }
  if (stage === "deployment" && Number.isFinite(Number(output.risk_score))) {
    badges.push({ at: "deployment", text: `risk ${formatNumber(output.risk_score, 2)}`, tone: "info" });
  }
  return badges;
}

function timeLabelFor(message, startMs, clock) {
  const label = message?.content?.time_label || message?.time_label;
  if (label) return label;
  if (clock) return message?.occurred_at ? formatTime(message.occurred_at) : "";
  const at = toDate(message?.occurred_at);
  return at && Number.isFinite(startMs) ? formatOffset((at.getTime() - startMs) / 1000) : "";
}

/**
 * One frame per message. `startStages` lets live mode continue from what is on screen, and
 * `clock` labels live frames with the WIB time instead of "T+" since the first message.
 * The returned frames carry their own copies of the state, so they can be replayed in any order.
 */
export function framesFromMessages(messages, { policy = DEFAULT_POLICY, startStages, prefix = "m", clock = false } = {}) {
  const states = { ...blankStates(), ...(startStages || {}) };
  const startMs = toDate(messages?.[0]?.occurred_at)?.getTime();
  const badges = new Map(); // keeps the latest badge per place
  let bids = [];
  let openGate = null;
  let marker = { stage: "intake", label: "" };
  let loop = false;

  return (messages || []).map((message, index) => {
    const content = message?.content || {};
    const output = content.output && typeof content.output === "object" ? content.output : content;
    const decision = content.decision || content.output?.decision;
    const performative = message?.performative || "inform";
    const contractNet = CONTRACT_NET.has(performative);
    const sender = message?.sender || "";
    const to = recipients(message);
    const person = sender.startsWith("Human-") || !isAgentName(sender);
    const toPerson = to.some((name) => name.startsWith("Human-") || !isAgentName(name));
    const stage = content.stage || (contractNet ? "assignment" : null) || stageOfAgent(sender) || gateInfo(content.checkpoint)?.stage || null;
    let gate = openGate;
    let caption = messageMeaning(message);
    loop = false;

    if (person && decision) {
      // A human decision resolves the open gate.
      const gateId = content.checkpoint || openGate?.id || defaultGateForStage[stage] || null;
      const gateStage = gateInfo(gateId)?.stage || openGate?.stage || stage;
      if (decision === "accepted") {
        gate = { id: gateId, stage: gateStage, state: "passed" };
        openGate = null;
        if (gateId === "canary_review") setState(states, gateStage, "active");
        else {
          completeBefore(states, gateStage);
          setState(states, gateStage, "done");
          const next = stageOfAgent(to[0]);
          if (next && stageIds.indexOf(next) > stageIds.indexOf(gateStage)) {
            completeBefore(states, next);
            setState(states, next, "active");
            marker = { stage: next, label: "" };
          }
        }
      } else if (decision === "rejected") {
        gate = { id: gateId, stage: gateStage, state: "stopped" };
        openGate = null;
        states[gateStage] = "stopped";
        marker = { stage: gateStage, label: "Stopped" };
      } else if (decision === "clarification_requested") {
        caption = `The agent needs a clearer note: ${content.question || content.interpretation?.clarification_question || "please clarify the change."}`;
      } else {
        // request_changes / changes_requested: the agent revises, the gate stays open.
        states[gateStage] = states[gateStage] === "stopped" ? "stopped" : "revising";
        gate = { id: gateId, stage: gateStage, state: "revising" };
        openGate = gate;
        marker = { stage: gateStage, label: "Revising" };
      }
    } else if (decision === "escalated") {
      const gateStage = stage && stage !== "assignment" ? stage : "triage";
      const gateId = content.checkpoint || defaultGateForStage[gateStage] || "autonomy_gate";
      completeBefore(states, gateStage);
      setState(states, gateStage, "waiting");
      gate = openGate = { id: gateId, stage: gateStage, state: "waiting" };
      marker = { stage: gateStage, label: "Waiting" };
    } else if (decision === "linked_duplicate") {
      completeBefore(states, "triage");
      setState(states, "triage", "done");
      stageIds.slice(stageIds.indexOf("triage") + 1).forEach((id) => {
        if (states[id] === "upcoming") states[id] = "skipped";
      });
      badges.set("triage", { at: "triage", text: `Duplicate of ${content.parent_ticket_id || "an older ticket"}`, tone: "warn" });
      gate = openGate = null;
      marker = { stage: "triage", label: "Closed" };
    } else if (contractNet) {
      completeBefore(states, "assignment");
      setState(states, "assignment", "active");
      marker = { stage: "assignment", label: "" };
      if (performative === "cfp") bids = [];
      if (performative === "propose") {
        bids = [...bids.filter((bid) => bid.worker !== sender), { worker: sender, utility: Number(content.utility), winner: false }];
      }
      if (performative === "accept-proposal") {
        const winner = content.worker_id || to[0];
        bids = bids.map((bid) => ({ ...bid, winner: bid.worker === winner }));
        if (!bids.some((bid) => bid.winner)) bids.push({ worker: winner, utility: Number(content.utility), winner: true });
        badges.set("assignment", { at: "assignment", text: `${workerBadge(winner)} · ${formatNumber(content.utility, 2)}`, tone: "accent" });
      }
    } else if (stage) {
      // A stage shares its result with whoever acts next.
      completeBefore(states, stage);
      const next = to.map((name) => stageOfAgent(name)).find(Boolean);
      const decisions = Array.isArray(output.decisions) ? output.decisions : [];
      if (toPerson) {
        const gateId = content.checkpoint || decisions.find((item) => item && item.autonomous === false)?.gate || defaultGateForStage[stage] || null;
        setState(states, stage, "waiting");
        gate = openGate = { id: gateId, stage, state: "waiting" };
        marker = { stage, label: "Waiting" };
      } else if (stage === "monitoring" && next === "triage") {
        setState(states, "monitoring", "done");
        loop = true;
        marker = { stage: "monitoring", label: "Loop" };
      } else if (next && stageIds.indexOf(next) > stageIds.indexOf(stage)) {
        setState(states, stage, "done");
        completeBefore(states, next);
        setState(states, next, "active");
        marker = { stage: next, label: "" };
        if (openGate?.stage === stage) gate = openGate = null;
      } else {
        setState(states, stage, "active");
        marker = { stage, label: "" };
      }
      badgesFromOutput(stage, output, policy).forEach((badge) => badges.set(badge.at, badge));
    }

    const envelopes = to.map((receiver, position) => ({
      id: `${message?.message_id || index}-${position}`,
      from: agentAnchor(sender, { contractNet }),
      to: agentAnchor(receiver, { contractNet }),
      performative,
      delay: position * 80,
    }));
    return {
      id: `${prefix}-${message?.message_id || index}`,
      stages: { ...states },
      marker: { ...marker },
      envelopes,
      gate: gate ? { ...gate } : null,
      loop,
      badges: [...badges.values()],
      bids: contractNet ? bids.map((bid) => ({ ...bid, anchor: agentAnchor(bid.worker, { contractNet: true }) })) : [],
      caption,
      timeLabel: timeLabelFor(message, startMs, clock),
      durationMs: contractNet ? 850 : person ? 1300 : 1100,
      source: message,
    };
  });
}

/** The Overview replay: an intro frame, one frame per message, then an outro with the loop. */
export function replayFrames(messages, { intro, outro, policy = DEFAULT_POLICY } = {}) {
  const frames = framesFromMessages(messages, { policy, prefix: "replay" });
  const first = {
    id: "replay-intro",
    stages: blankStates(),
    marker: { stage: "intake", label: "" },
    envelopes: [{ id: "intro-0", from: "channels", to: "intake", performative: "feedback", delay: 0 }],
    gate: null,
    loop: false,
    badges: [],
    bids: [],
    caption: intro?.caption || "Feedback arrives from users.",
    timeLabel: intro?.timeLabel || "",
    durationMs: 1800,
  };
  const last = frames.at(-1);
  const end = last && {
    ...last,
    id: "replay-outro",
    stages: Object.fromEntries(stageIds.map((id) => [id, "done"])),
    marker: { stage: "monitoring", label: "Loop" },
    envelopes: [],
    gate: null,
    loop: true,
    bids: [],
    caption: outro?.caption || "The loop returns to Triage.",
    timeLabel: outro?.timeLabel || last.timeLabel,
    durationMs: 2000,
    source: null,
  };
  return [first, ...frames, ...(end ? [end] : [])];
}

/** The single frame that matches a ticket snapshot (used when no animation is queued). */
export function frameFromSnapshot(raw, policy = DEFAULT_POLICY) {
  const record = normalizeSnapshot(raw);
  const states = blankStates();
  record.stages.forEach((entry) => {
    states[entry.name] =
      { completed: "done", rejected: "stopped", skipped: "skipped", upcoming: "upcoming" }[entry.status] ||
      (record.status === "waiting_for_review" ? "waiting" : "active");
  });
  if (record.status === "completed") stageIds.forEach((id) => (states[id] = "done"));
  if (record.status === "duplicate") {
    stageIds.forEach((id, index) => {
      if (index <= stageIds.indexOf(record.current_stage)) states[id] = "done";
      else states[id] = "skipped";
    });
  }
  const badges = [];
  Object.entries(record.agent_outputs).forEach(([stage, output]) => badges.push(...badgesFromOutput(stage, output, policy)));
  if (record.duplicate_of) {
    const index = badges.findIndex((badge) => badge.at === "triage");
    const badge = { at: "triage", text: `Duplicate of ${record.duplicate_of}`, tone: "warn" };
    if (index >= 0) badges[index] = badge;
    else badges.push(badge);
  }
  let gate = null;
  if (record.pending_gate) gate = { id: record.pending_gate.gate, stage: record.pending_gate.stage, state: "waiting" };
  if (record.status === "rejected") {
    const last = record.reviews.at(-1);
    gate = { id: last?.checkpoint || null, stage: record.current_stage, state: "stopped" };
  }
  const stage = stageInfo(record.current_stage);
  const agent = shortAgentName(record.assignee && record.current_stage === "investigation" ? record.assignee : stage.agent);
  const question = clarificationQuestion(record);
  // The backend's current stage is the one that runs at the next advance; only intake has
  // already run when a ticket is created.
  const caption =
    record.status === "waiting_for_review"
      ? question
        ? `The agent needs a clearer note: ${question}`
        : `Waiting for a human: ${gateLabel(record.pending_gate?.gate, policy)}.`
      : record.status === "completed"
        ? "Finished: all nine stages ran in the prototype, and Monitoring handed its result back to Triage."
        : record.status === "rejected"
          ? `Stopped by the reviewer at ${stage.name}.`
          : record.status === "duplicate"
            ? `Linked as a duplicate of ${record.duplicate_of || "an older ticket"}; this run is closed.`
            : record.agent_outputs[record.current_stage]
              ? `${stage.name} (${agent}) has shared its result; the ticket moves on at the next step.`
              : `Up next: ${stage.name} (${agent}).`;
  return {
    id: `snapshot-${record.ticket_id}-${record.current_stage}-${record.status}-${record.reviews.length}`,
    stages: states,
    marker: { stage: record.current_stage, label: record.status === "running" ? "" : statusLabel(record.status) },
    envelopes: [],
    gate,
    loop: record.status === "completed",
    badges,
    bids: [],
    caption,
    timeLabel: "",
    durationMs: 0,
  };
}

/** Add frames to the live queue, keeping only the newest `cap` so the animation never lags far behind. */
export function enqueueFrames(queue, frames, cap = 8) {
  return [...(queue || []), ...(frames || [])].slice(-cap);
}

/** A sentence for screen readers and the SVG <desc>. */
export function describeFrame(frame, policy = DEFAULT_POLICY) {
  if (!frame) return "No step selected.";
  const states = stages
    .map((stage) => `${stage.name}: ${(stateLabel[frame.stages?.[stage.id]] || "Upcoming").toLowerCase()}`)
    .join("; ");
  const gate = frame.gate?.id ? ` Human gate "${gateLabel(frame.gate.id, policy)}" is ${frame.gate.state}.` : "";
  const loop = frame.loop ? " The feedback loop returns to Triage." : "";
  return `${frame.caption || ""}${gate}${loop} Stages: ${states}.`.trim();
}
