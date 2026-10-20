import test from "node:test";
import assert from "node:assert/strict";
import {
  canaryAllowed,
  DEFAULT_POLICY,
  duplicateBand,
  gateEvidence,
  gateLabel,
  gateOutcome,
  gateRule,
  normalizePolicy,
  policySourceLabel,
  reviewPriority,
} from "./policy.js";

test("gateOutcome mirrors evaluate_gate", () => {
  assert.deepEqual(gateOutcome(0.88, "Critical"), { autonomous: false, reason: "risk_too_high", risk: 1 });
  assert.deepEqual(gateOutcome(0.65, "Low"), { autonomous: false, reason: "low_confidence", risk: 0.1 });
  assert.deepEqual(gateOutcome(0.7, "High"), { autonomous: true, reason: "autonomous", risk: 0.6 });
  assert.equal(gateOutcome(0.9, "Unknown").reason, "unknown");
});

test("duplicateBand uses the two cosine bands", () => {
  assert.equal(duplicateBand(0.91), "auto_link");
  assert.equal(duplicateBand(0.85), "auto_link");
  assert.equal(duplicateBand(0.78), "review");
  assert.equal(duplicateBand(0.7), "review");
  assert.equal(duplicateBand(0.69), "new");
});

test("canaryAllowed starts alone only at or below the canary risk limit", () => {
  assert.equal(canaryAllowed(0.28), true);
  assert.equal(canaryAllowed(0.3), true);
  assert.equal(canaryAllowed(0.31), false);
});

test("reviewPriority weighs severity risk by minutes waiting", () => {
  const now = Date.parse("2026-10-20T02:00:00Z");
  const critical = reviewPriority({ severity: "Critical", review_requested_at: "2026-10-20T01:50:00Z" }, DEFAULT_POLICY, now);
  const low = reviewPriority({ severity: "Low", review_requested_at: "2026-10-20T00:00:00Z" }, DEFAULT_POLICY, now);
  assert.equal(critical.waitingMinutes, 10);
  assert.equal(critical.score, 10);
  assert.ok(Math.abs(low.score - 12) < 1e-9);
  assert.equal(reviewPriority({ severity: "High" }, DEFAULT_POLICY, now).waitingMinutes, 1);
});

test("normalizePolicy merges a partial response over the defaults", () => {
  const policy = normalizePolicy({ tau: 0.8, duplicate: { review: 0.75 }, canary_risk_max: 0.25, gates: [{ gate: "pr_merge", label: "Check the PR" }] });
  assert.equal(policy.tau, 0.8);
  assert.equal(policy.risk_max, DEFAULT_POLICY.risk_max);
  assert.equal(policy.duplicate.review, 0.75);
  assert.equal(policy.duplicate.auto_link, DEFAULT_POLICY.duplicate.auto_link);
  assert.equal(policy.canary.risk_max, 0.25);
  assert.equal(policy.source, "server");
  assert.equal(gateLabel("pr_merge", policy), "Check the PR");
  assert.equal(gateLabel("release_signoff", policy), "Approve the full release");
  assert.equal(normalizePolicy(null), DEFAULT_POLICY);
});

test("gateEvidence explains each gate with value and limit", () => {
  const autonomy = gateEvidence({
    severity: "Critical",
    pending_gate: { gate: "autonomy_gate", evidence: { confidence: 0.88, tau: 0.7, risk: 1, risk_max: 0.6 } },
    agent_outputs: { triage: { severity: "Critical" } },
  });
  assert.equal(autonomy.rows[0].ok, true);
  assert.equal(autonomy.rows[1].ok, false);
  const duplicate = gateEvidence({ pending_gate: { gate: "duplicate_review" }, agent_outputs: { triage: { duplicate: { best_match: { ticket_id: "TCK-1", cosine: 0.78 } } } } });
  assert.match(duplicate.rows[0].label, /TCK-1/);
  assert.equal(duplicate.rows[0].value, "0.78");
  const canary = gateEvidence({ pending_gate: { gate: "canary_review" }, agent_outputs: { deployment: { risk_score: 0.42 } } });
  assert.equal(canary.rows[0].ok, false);
  const secret = gateEvidence({ pending_gate: { gate: "secret_scan" }, agent_outputs: { implementation: { security_precheck: { findings: [{}, {}] } } } });
  assert.equal(secret.rows[0].value, "2");
  const merge = gateEvidence({ pending_gate: { gate: "pr_merge" }, agent_outputs: { qa: { selected_tests: 120, suite_size: 3400, duration_minutes: 7.5, budget_minutes: 8, failed: 0, napfd: 0.81 } } });
  assert.equal(merge.rows.length, 3);
  assert.ok(merge.rows.every((row) => row.ok !== false));
  const release = gateEvidence({ pending_gate: { gate: "release_signoff" }, agent_outputs: { deployment: { canary: { status: "passed" }, risk_score: 0.2 } } });
  assert.equal(release.rows[0].ok, true);
});

test("gateRule prefers the server's wording and falls back to the policy numbers", () => {
  const server = normalizePolicy({ gates: [{ gate: "pr_merge", autonomous_when: "never", human_when: "always (server)" }] });
  assert.equal(gateRule("pr_merge", server).human, "always (server)");
  assert.match(gateRule("autonomy_gate").autonomous, /confidence ≥ 0\.70 and risk ≤ 0\.60/);
  assert.match(gateRule("canary_review", normalizePolicy({ canary: { risk_max: 0.25 } })).human, /> 0\.25/);
  assert.match(policySourceLabel(DEFAULT_POLICY), /dashboard fallback/);
  assert.match(policySourceLabel(normalizePolicy({ policy_id: "p-2", source: "database" })), /^Policy p-2 · from the database$/);
});
