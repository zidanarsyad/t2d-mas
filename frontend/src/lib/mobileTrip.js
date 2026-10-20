// The Scout-Log trip: the report's cost model (static pull vs mobile agent) and helpers
// that turn real node visits into the same "trip" shape the animation draws.
import { DEFAULT_POLICY } from "./policy.js";
import { formatNumber } from "./format.js";

/** The six data nodes, one service each (same order as agents/tools.py). */
export const NODE_SERVICES = ["api-gateway", "order-service", "payment-db", "auth-service", "search-service", "notification-service"];

/**
 * Scenario inputs from the report's worked example (TCK-1042).
 * Sizes of the agent bundle and its result come from the policy, not from here.
 */
export const REPORT_INPUTS = Object.freeze({
  nodes: 6,
  logMbPerNode: 1365, // raw logs in the incident window, per node
  linkMbPerSecond: 12.5, // a 100 Mbit/s link to the orchestrator
  nodeScanSeconds: 20, // the analysis runs on all nodes in parallel
});

const MB = 1e6;

/** Bytes and seconds for both strategies, plus the break-even and the migrate rule. */
export function mobileCostModel(inputs = REPORT_INPUTS, policy = DEFAULT_POLICY) {
  const { nodes, logMbPerNode, linkMbPerSecond, nodeScanSeconds } = { ...REPORT_INPUTS, ...inputs };
  const agentMb = policy.migration.agent_bundle_mb;
  const resultMb = policy.migration.result_mb;
  const staticMb = nodes * logMbPerNode;
  const sentMb = nodes * agentMb;
  const returnedMb = nodes * resultMb;
  const mobileMb = sentMb + returnedMb;
  const staticSeconds = staticMb / linkMbPerSecond;
  const dispatchSeconds = sentMb / linkMbPerSecond;
  const returnSeconds = returnedMb / linkMbPerSecond;
  const mobileSeconds = dispatchSeconds + nodeScanSeconds + returnSeconds;
  return {
    inputs: { nodes, logMbPerNode, linkMbPerSecond, nodeScanSeconds, agentMb, resultMb, factor: policy.migration.factor },
    static: { mb: staticMb, seconds: staticSeconds },
    mobile: { mb: mobileMb, sentMb, returnedMb, seconds: mobileSeconds, dispatchSeconds, returnSeconds },
    savedPercent: (1 - mobileMb / staticMb) * 100,
    speedup: staticSeconds / mobileSeconds,
    // Moving the agent saves bytes once a node holds more than bundle + result.
    breakEvenMb: agentMb + resultMb,
    // The prototype only migrates when the node holds a clear margin more (rule from the report).
    migrateThresholdMb: (agentMb + resultMb) * policy.migration.factor,
  };
}

/** n points on a circle, starting at the top and going clockwise. */
export function ringPositions(count, cx, cy, radius) {
  return Array.from({ length: count }, (_, index) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
    return { x: Number((cx + radius * Math.cos(angle)).toFixed(2)), y: Number((cy + radius * Math.sin(angle)).toFixed(2)) };
  });
}

/**
 * The phases of one trip. `counterMb` and `seconds` are the totals reached at the end of
 * each phase (simulated seconds, not wall time); `durationMs` is the animation length.
 */
export function tripSteps(model, mode = "mobile") {
  const { inputs } = model;
  if (mode === "static") {
    return [
      { id: "pull", label: "Pull raw logs", durationMs: 3200, counterMb: model.static.mb, seconds: model.static.seconds,
        caption: `The central server downloads every raw log: ${inputs.nodes} nodes × ${formatNumber(inputs.logMbPerNode)} MB, personal data included.` },
      { id: "done", label: "Done", durationMs: 1600, counterMb: model.static.mb, seconds: model.static.seconds,
        caption: "All raw data left the nodes before any analysis could start." },
    ];
  }
  return [
    { id: "sign", label: "Sign", durationMs: 700, counterMb: 0, seconds: 0,
      caption: `The orchestrator signs the Scout-Log bundle (${inputs.agentMb} MB of code and state).` },
    { id: "dispatch", label: "Dispatch", durationMs: 1100, counterMb: model.mobile.sentMb, seconds: model.mobile.dispatchSeconds,
      caption: `One signed bundle travels to each of the ${inputs.nodes} nodes.` },
    { id: "execute", label: "Run on the node", durationMs: 1400, counterMb: model.mobile.sentMb, seconds: model.mobile.dispatchSeconds + inputs.nodeScanSeconds,
      caption: `Each node checks the signature and runs the analysis in a sandbox. ${formatNumber(inputs.logMbPerNode)} MB of raw logs stay on each node.` },
    { id: "return", label: "Return", durationMs: 1100, counterMb: model.mobile.mb, seconds: model.mobile.seconds,
      caption: `Only allow-listed aggregates come back: ${inputs.resultMb} MB per node.` },
    { id: "done", label: "Done", durationMs: 1600, counterMb: model.mobile.mb, seconds: model.mobile.seconds,
      caption: "The raw data never left the nodes; only the summary travelled." },
  ];
}

/** The model as a trip: six nodes with the report's sizes (all numbers in bytes). */
export function modelTrip(model) {
  const { inputs } = model;
  return {
    source: "model",
    nodes: NODE_SERVICES.slice(0, inputs.nodes).map((service, index) => ({
      node_id: `node-${index + 1}`,
      service,
      mode: "mobile_agent",
      status: "returned",
      logBytes: inputs.logMbPerNode * MB,
      shouldMigrate: inputs.logMbPerNode > model.migrateThresholdMb,
      bytesSent: inputs.agentMb * MB,
      bytesReturned: inputs.resultMb * MB,
      aggregate: null,
      error: null,
    })),
  };
}

function nodeFromVisit(visit, index) {
  const failed = !visit || visit.mode === "failed" || Boolean(visit.error);
  const rule = visit?.migration_rule || {};
  return {
    node_id: visit?.node_id || visit?.node || `node-${index + 1}`,
    service: visit?.service || NODE_SERVICES[index] || "unknown",
    mode: visit?.mode || (failed ? "failed" : "mobile_agent"),
    status: failed ? "failed" : "returned",
    logBytes: Number(visit?.log_bytes_kept ?? (rule.log_mb ? rule.log_mb * MB : 0)) || 0,
    shouldMigrate: rule.should_migrate ?? null,
    rule,
    bytesSent: Number(visit?.bytes_sent) || 0,
    bytesReturned: Number(visit?.bytes_returned) || 0,
    aggregate: visit?.aggregate ?? visit?.result ?? null,
    error: visit?.error || null,
  };
}

/** A trip from the investigation stage of a ticket snapshot; null when there are no visits yet. */
export function tripFromSnapshot(record) {
  const visits = record?.agent_outputs?.investigation?.node_visits;
  if (!Array.isArray(visits) || !visits.length) return null;
  return { source: "live", ticketId: record.ticket_id, nodes: visits.map(nodeFromVisit) };
}

/** A trip from `Promise.allSettled` over POST /demo/migrate/1..6; rejected calls become failed nodes. */
export function tripFromMigrations(results) {
  return {
    source: "live",
    nodes: (results || []).map((result, index) =>
      result?.status === "fulfilled"
        ? nodeFromVisit(result.value, index)
        : { ...nodeFromVisit({ mode: "failed", error: result?.reason?.message || "No response" }, index), service: NODE_SERVICES[index] || "unknown" },
    ),
  };
}

/** One SSE `agent.migrated` event as a trip node (the event has the visit's numbers, not the aggregate). */
export function nodeFromMigrationEvent(event) {
  const index = NODE_SERVICES.indexOf(event?.service);
  return {
    ...nodeFromVisit(
      { node_id: event?.node_id, service: event?.service, mode: event?.mode, bytes_sent: event?.bytes_sent, bytes_returned: event?.bytes_returned, log_bytes_kept: event?.log_bytes, migration_rule: { should_migrate: event?.should_migrate } },
      index >= 0 ? index : 0,
    ),
  };
}

/** Totals for the trip log and the byte counter. */
export function tripTotals(trip) {
  const nodes = trip?.nodes || [];
  return {
    nodes: nodes.length,
    returned: nodes.filter((node) => node.status === "returned").length,
    failed: nodes.filter((node) => node.status === "failed").length,
    bytesMoved: nodes.reduce((sum, node) => sum + node.bytesSent + node.bytesReturned, 0),
    bytesKept: nodes.reduce((sum, node) => sum + node.logBytes, 0),
  };
}
