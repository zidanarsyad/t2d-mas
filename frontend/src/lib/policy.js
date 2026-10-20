// Policy thresholds and the gate rules, mirrored from agents/policy.py and triage/gate.py.
// The live values come from GET /policy; DEFAULT_POLICY is only the offline fallback.
// This is the only frontend file allowed to contain threshold numbers.
import { gates as defaultGates, gateInfo } from "./workflow.js";
import { formatNumber } from "./format.js";

export const DEFAULT_POLICY = Object.freeze({
  policy_id: "default-v1",
  source: "default",
  // Autonomy gate: act alone only if confidence >= tau AND risk <= risk_max.
  tau: 0.7,
  risk_max: 0.6,
  risk_by_class: { Low: 0.1, Medium: 0.3, High: 0.6, Critical: 1.0 },
  // Cosine similarity bands: >= auto_link links the duplicate, >= review asks a person.
  duplicate: { auto_link: 0.85, review: 0.7 },
  canary: { percent: 5, risk_max: 0.3, observe_minutes: 30 },
  // Mobile agent migrates when node log volume > (bundle + result) * factor.
  migration: { factor: 3, agent_bundle_mb: 12, result_mb: 2 },
  ci: { budget_minutes: 8 },
  monitoring: { anomaly_z: 3 },
  sla_hours: { Critical: 2, High: 8, Medium: 72, Low: 168 },
  gates: defaultGates.map((gate) => ({ gate: gate.id, label: gate.label, stage: gate.stage, agent: gate.agent, reversible: !gate.irreversible })),
  irreversible_actions: ["merge", "full_deploy"],
});

const num = (value, fallback) =>
  value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) ? Number(value) : fallback;

function mergeGates(rawGates) {
  const merged = DEFAULT_POLICY.gates.map((gate) => ({ ...gate }));
  (Array.isArray(rawGates) ? rawGates : []).forEach((item) => {
    const id = item?.gate || item?.id;
    if (!id) return;
    const existing = merged.find((gate) => gate.gate === id);
    if (existing) Object.assign(existing, Object.fromEntries(Object.entries(item).filter(([, value]) => value !== null && value !== undefined)), { gate: id });
    else merged.push({ ...item, gate: id });
  });
  return merged;
}

/**
 * Merge a (possibly partial or older) /policy response over the defaults.
 * Flat names such as `duplicate_auto_link` are accepted too, to absorb API drift.
 */
export function normalizePolicy(raw) {
  if (!raw || typeof raw !== "object") return DEFAULT_POLICY;
  const d = DEFAULT_POLICY;
  return {
    policy_id: raw.policy_id || d.policy_id,
    source: raw.source || "server",
    tau: num(raw.tau, d.tau),
    risk_max: num(raw.risk_max, d.risk_max),
    risk_by_class: { ...d.risk_by_class, ...(raw.risk_by_class || {}) },
    duplicate: {
      auto_link: num(raw.duplicate?.auto_link ?? raw.duplicate_auto_link, d.duplicate.auto_link),
      review: num(raw.duplicate?.review ?? raw.duplicate_review, d.duplicate.review),
    },
    canary: {
      percent: num(raw.canary?.percent ?? raw.canary_percent, d.canary.percent),
      risk_max: num(raw.canary?.risk_max ?? raw.canary_risk_max, d.canary.risk_max),
      observe_minutes: num(raw.canary?.observe_minutes ?? raw.canary_observe_minutes, d.canary.observe_minutes),
    },
    migration: {
      factor: num(raw.migration?.factor ?? raw.migration_factor, d.migration.factor),
      agent_bundle_mb: num(raw.migration?.agent_bundle_mb ?? raw.agent_bundle_mb, d.migration.agent_bundle_mb),
      result_mb: num(raw.migration?.result_mb ?? raw.result_mb, d.migration.result_mb),
    },
    ci: { budget_minutes: num(raw.ci?.budget_minutes ?? raw.ci_budget_minutes, d.ci.budget_minutes) },
    monitoring: { anomaly_z: num(raw.monitoring?.anomaly_z ?? raw.anomaly_z, d.monitoring.anomaly_z) },
    sla_hours: { ...d.sla_hours, ...(raw.sla_hours || {}) },
    gates: mergeGates(raw.gates),
    irreversible_actions: Array.isArray(raw.irreversible_actions) ? raw.irreversible_actions : d.irreversible_actions,
  };
}

export function gateLabel(gateId, policy = DEFAULT_POLICY) {
  return policy.gates?.find((gate) => gate.gate === gateId)?.label || gateInfo(gateId)?.label || "Human review";
}

/** Same rule as evaluate_gate: autonomous only when confidence >= tau AND risk <= risk_max. */
export function gateOutcome(confidence, severity, policy = DEFAULT_POLICY) {
  const risk = policy.risk_by_class?.[severity];
  const score = Number(confidence);
  if (risk === undefined || !Number.isFinite(score)) return { autonomous: false, reason: "unknown", risk: risk ?? null };
  const autonomous = score >= policy.tau && risk <= policy.risk_max;
  const reason = autonomous ? "autonomous" : score < policy.tau ? "low_confidence" : "risk_too_high";
  return { autonomous, reason, risk };
}

export const gateReasonLabel = {
  autonomous: "Confident and low risk: the agent may continue",
  low_confidence: "Confidence is below τ",
  risk_too_high: "Risk is above R_max",
  canary_risk: "Release risk is above the canary limit",
  canary_failed: "The canary broke an SLO",
  secret_found: "A secret was found in the change",
  always: "This step always needs a person",
  new: "No similar earlier ticket",
  review: "Similar enough that a person should decide",
  auto_link: "Near-identical to an earlier ticket",
  reviewer_marked_new: "A reviewer marked it as a new issue",
  unknown: "Not enough information",
};

/** Cosine similarity -> "auto_link" | "review" | "new". */
export function duplicateBand(score, policy = DEFAULT_POLICY) {
  const value = Number(score);
  if (!Number.isFinite(value)) return "new";
  if (value >= policy.duplicate.auto_link) return "auto_link";
  if (value >= policy.duplicate.review) return "review";
  return "new";
}

export const duplicateBandLabel = {
  auto_link: "Duplicate: linked automatically",
  review: "Possible duplicate: a person decides",
  new: "New issue",
};

/** A small canary may start without a person only when the release risk is low enough. */
export function canaryAllowed(riskScore, policy = DEFAULT_POLICY) {
  const value = Number(riskScore);
  return Number.isFinite(value) && value <= policy.canary.risk_max;
}

/** Sort key for the review inbox: severity risk × minutes waiting (at least one minute). */
export function reviewPriority(record, policy = DEFAULT_POLICY, now = Date.now()) {
  const risk = policy.risk_by_class?.[record?.severity] ?? policy.risk_by_class.Medium;
  const since = Date.parse(record?.review_requested_at || record?.created_at || "");
  const waitingMinutes = Number.isFinite(since) ? Math.max(1, (now - since) / 60000) : 1;
  return { score: risk * waitingMinutes, risk, waitingMinutes };
}

const two = (value) => formatNumber(value, 2);

/** When a gate lets the agent continue and when it asks a person: from /policy, or built from the numbers. */
export function gateRule(gateId, policy = DEFAULT_POLICY) {
  const server = policy.gates?.find((gate) => gate.gate === gateId);
  if (server?.autonomous_when && server?.human_when) return { autonomous: server.autonomous_when, human: server.human_when };
  const rules = {
    duplicate_review: {
      autonomous: `similarity ≥ ${two(policy.duplicate.auto_link)} (link) or < ${two(policy.duplicate.review)} (new ticket)`,
      human: `${two(policy.duplicate.review)} ≤ similarity < ${two(policy.duplicate.auto_link)}`,
    },
    autonomy_gate: { autonomous: `confidence ≥ ${two(policy.tau)} and risk ≤ ${two(policy.risk_max)}`, human: "low confidence or high risk (Critical is always high risk)" },
    secret_scan: { autonomous: "no secret found in the draft change", human: "a secret is found; it can only be redrafted or stopped" },
    pr_merge: { autonomous: "never", human: "always: merging needs a code review" },
    canary_review: { autonomous: `release risk score ≤ ${two(policy.canary.risk_max)}`, human: `release risk score > ${two(policy.canary.risk_max)}` },
    release_signoff: { autonomous: "never", human: "always: a full deploy needs a release sign-off" },
  };
  return rules[gateId] || { autonomous: "—", human: "—" };
}

/** "Policy default-v1 · from the database" — where the thresholds on screen come from. */
export function policySourceLabel(policy = DEFAULT_POLICY) {
  const where = { database: "from the database", code_defaults: "backend code defaults", default: "dashboard fallback (backend not reachable)" }[policy.source] || "from the backend";
  return `Policy ${policy.policy_id} · ${where}`;
}

/**
 * The evidence a reviewer needs at the pending gate: rows of value vs limit, plus a note.
 * `ok` is true when the rule passed, false when it failed, null when it is informational.
 */
export function gateEvidence(record, policy = DEFAULT_POLICY) {
  const gate = record?.pending_gate?.gate || record?.waiting_for;
  const evidence = record?.pending_gate?.evidence || {};
  const outputs = record?.agent_outputs || {};
  const rows = [];
  let note = "";
  if (gate === "autonomy_gate") {
    const triage = outputs.triage || {};
    const decision = (triage.decisions || []).find((item) => item.gate === "autonomy_gate")?.inputs || {};
    const confidence = num(evidence.confidence ?? decision.confidence ?? triage.confidence ?? record?.severity_confidence, null);
    const tau = num(evidence.tau ?? decision.tau, policy.tau);
    const riskMax = num(evidence.risk_max ?? decision.risk_max, policy.risk_max);
    const severity = triage.severity || record?.severity;
    const risk = num(evidence.risk ?? decision.risk, policy.risk_by_class?.[severity] ?? null);
    rows.push({ label: "Confidence", term: "tau", value: two(confidence), limit: `at least ${two(tau)} (τ)`, ok: confidence !== null ? confidence >= tau : null });
    rows.push({ label: `Risk of a ${severity || "unknown"} ticket`, term: "risk-max", value: two(risk), limit: `at most ${two(riskMax)} (R_max)`, ok: risk !== null ? risk <= riskMax : null });
    note = "Both rules must pass for the agent to continue alone. Critical tickets always carry the highest risk.";
  } else if (gate === "duplicate_review") {
    const match = outputs.triage?.duplicate?.best_match || {};
    const cosine = num(evidence.cosine ?? match.cosine, null);
    rows.push({ label: `Similarity to ${match.ticket_id || "the closest ticket"}`, term: "duplicate-bands", value: two(cosine), limit: `${two(policy.duplicate.review)} – ${two(policy.duplicate.auto_link)}`, ok: null });
    note = `Below ${two(policy.duplicate.review)} it would be a new ticket; from ${two(policy.duplicate.auto_link)} it would be linked automatically. In between, a person decides.`;
  } else if (gate === "secret_scan") {
    const findings = outputs.implementation?.security_precheck?.findings || [];
    rows.push({ label: "Secrets found in the draft change", value: String(findings.length || evidence.findings || 1), limit: "0", ok: false });
    note = "A change with a secret can only be redrafted or stopped, never approved.";
  } else if (gate === "pr_merge") {
    const qa = outputs.qa || {};
    rows.push({ label: "Tests selected", value: qa.selected_tests !== undefined ? `${formatNumber(qa.selected_tests)} of ${formatNumber(qa.suite_size)}` : "—", limit: `within ${policy.ci.budget_minutes} min`, ok: qa.duration_minutes !== undefined ? qa.duration_minutes <= num(qa.budget_minutes, policy.ci.budget_minutes) : null });
    rows.push({ label: "Failed tests", value: qa.failed !== undefined ? String(qa.failed) : "—", limit: "0", ok: qa.failed !== undefined ? qa.failed === 0 : null });
    if (qa.napfd !== undefined) rows.push({ label: "Test order quality", term: "napfd", value: two(qa.napfd), limit: "closer to 1 is better", ok: null });
    note = "Merging is irreversible, so a person always reviews the change.";
  } else if (gate === "canary_review") {
    const risk = num(evidence.risk_score ?? outputs.deployment?.risk_score, null);
    rows.push({ label: "Release risk score", term: "risk-score", value: two(risk), limit: `at most ${two(policy.canary.risk_max)} to start alone`, ok: risk !== null ? canaryAllowed(risk, policy) : null });
    note = `A ${policy.canary.percent}% canary starts on its own only for low-risk releases.`;
  } else if (gate === "release_signoff") {
    const deployment = outputs.deployment || {};
    rows.push({ label: "Canary", term: "canary", value: deployment.canary?.status ? String(deployment.canary.status).replaceAll("_", " ") : "—", limit: "passed", ok: deployment.canary?.status ? deployment.canary.status === "passed" : null });
    rows.push({ label: "Release risk score", term: "risk-score", value: two(deployment.risk_score), limit: "—", ok: null });
    note = "A full release is irreversible, so it always needs a person's sign-off.";
  }
  return { gate, label: gateLabel(gate, policy), rows, note };
}
