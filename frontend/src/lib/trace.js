// Decision-trace entries. Live ACL messages and saved audit events become the same shape:
//   { id, at, actor, receivers, performative, stage, kind, title, detail, decision, gate, raw }
// kind is one of: message, output, gate, decision, action, event.
import { gateInfo, isAgentName, messageMeaning, performativeLabel, recipients, stageInfo, stageOfAgent } from "./workflow.js";
import { DEFAULT_POLICY, gateLabel } from "./policy.js";
import { formatNumber } from "./format.js";

const CONTRACT_NET = new Set(["cfp", "propose", "accept-proposal", "reject-proposal"]);

function entry(fields) {
  return {
    id: fields.id,
    at: fields.at || null,
    actor: fields.actor || "Orchestrator",
    receivers: fields.receivers || [],
    performative: fields.performative || null,
    stage: fields.stage || null,
    kind: fields.kind || "event",
    title: fields.title || "Event",
    detail: fields.detail || "",
    decision: fields.decision || null,
    gate: fields.gate || null,
    raw: fields.raw ?? null,
  };
}

function messageEntry(message, index, policy) {
  const content = message?.content || {};
  const decision = content.decision || content.output?.decision || null;
  const performative = message?.performative || "inform";
  const person = !isAgentName(message?.sender) || String(message?.sender).startsWith("Human-");
  const stage = content.stage || (CONTRACT_NET.has(performative) ? "assignment" : null) || stageOfAgent(message?.sender) || gateInfo(content.checkpoint)?.stage || null;
  const gate = content.checkpoint || null;
  let kind = "message";
  let title = `${performativeLabel(performative)}${stage ? ` · ${stageInfo(stage).name}` : ""}`;
  if (person && decision) {
    kind = "decision";
    title = `Human decision: ${String(decision).replaceAll("_", " ")}${gate ? ` · ${gateLabel(gate, policy)}` : ""}`;
  } else if (decision === "escalated" || decision === "autonomous") {
    kind = "gate";
    title = decision === "escalated" ? "Policy check: a person must decide" : "Policy check: the agent may continue";
  }
  return entry({
    id: message?.message_id || `message-${index}`,
    at: message?.occurred_at,
    actor: message?.sender,
    receivers: recipients(message),
    performative,
    stage,
    kind,
    title,
    detail: messageMeaning(message),
    decision,
    gate,
    raw: message,
  });
}

export function entriesFromMessages(messages, policy = DEFAULT_POLICY) {
  return (messages || []).map((message, index) => messageEntry(message, index, policy));
}

/** Saved audit rows (GET /ticket-history) as trace entries; each message is shown once. */
export function entriesFromAudit(events, policy = DEFAULT_POLICY) {
  const entries = [];
  (events || []).forEach((event, index) => {
    const action = event?.action || "event";
    const id = `${event?.occurred_at || index}-${action}-${index}`;
    if (action === "agent_message") {
      if (event.decision && event.decision !== "published") return; // skip the "authorized" twin
      entries.push({
        ...messageEntry(
          { message_id: event.message_id || id, sender: event.agent, receiver: event.receivers || [], performative: event.performative, content: event.output || {}, occurred_at: event.occurred_at },
          index,
          policy,
        ),
        raw: event,
      });
      return;
    }
    const stage = event?.stage || gateInfo(event?.checkpoint)?.stage || stageOfAgent(event?.agent);
    if (action === "policy_gate") {
      const limits =
        event.confidence !== undefined && event.confidence !== null
          ? `Confidence ${formatNumber(event.confidence, 2)} vs τ ${formatNumber(event.tau ?? policy.tau, 2)}; risk ${formatNumber(event.risk, 2)} vs R_max ${formatNumber(event.risk_max ?? policy.risk_max, 2)}.`
          : "";
      entries.push(entry({ id, at: event.occurred_at, actor: event.agent, stage, kind: "gate", gate: event.checkpoint, decision: event.decision, title: `Policy check: ${gateLabel(event.checkpoint, policy)}`, detail: `${String(event.decision || "").replaceAll("_", " ")}. ${limits}`.trim(), raw: event }));
    } else if (["human_approval", "human_review_feedback", "review_revision_requested", "human_review"].includes(action)) {
      entries.push(entry({ id, at: event.occurred_at, actor: event.approver || event.agent, stage, kind: "decision", gate: event.checkpoint, decision: event.decision, title: `Human decision: ${String(event.intent || event.decision || "recorded").replaceAll("_", " ")}${event.checkpoint ? ` · ${gateLabel(event.checkpoint, policy)}` : ""}`, detail: event.note || "", raw: event }));
    } else if (action === "agent_output") {
      entries.push(entry({ id, at: event.occurred_at, actor: event.agent, stage, kind: "output", decision: event.decision, title: `${stageInfo(stage).name} result`, detail: event.output?.summary || `${event.agent} recorded its result (${String(event.execution_mode || "recorded").replaceAll("_", " ")}).`, raw: event }));
    } else if (["irreversible_action", "merge", "full_deploy", "canary", "deployment"].includes(action)) {
      entries.push(entry({ id, at: event.occurred_at, actor: event.agent, stage, kind: "action", decision: event.decision, title: `Action: ${action.replaceAll("_", " ")}`, detail: String(event.decision || "").replaceAll("_", " "), raw: event }));
    } else {
      entries.push(entry({ id, at: event.occurred_at, actor: event.agent, stage, kind: "event", decision: event.decision, title: action.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase()), detail: String(event.decision || "").replaceAll("_", " "), raw: event }));
    }
  });
  return entries;
}
