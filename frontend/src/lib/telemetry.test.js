import test from "node:test";
import assert from "node:assert/strict";
import { canaryAt, describeAnomaly, detectAnomalies, normalizeTelemetry, pivotSeries, sloStatus } from "./telemetry.js";

const raw = {
  scenario: "flash_sale",
  seed: 42,
  step_seconds: 60,
  services: [
    { service: "a", node_id: "node-1", series: { latency_p95_ms: [1, 2, 3], error_rate: [0, 0, 0], rps: [5, 5, 5] }, slo: { latency_p95_ms: 10, error_rate: 0.02 } },
    { service: "b", node_id: "node-2", series: { p95: [4, 5, 6] }, slo: { p95: 9 } },
  ],
  anomalies: [{ anomaly_id: "x", service: "a", metric: "latency_p95_ms", peak_minute: 2, peak_value: 3, baseline_mean: 1, z: 4.2 }],
  canary_steps: [{ minute: 50, percent: 50 }, { minute: 40, percent: 5, needs_human: false }],
};

test("normalizeTelemetry accepts older field names and sorts canary steps", () => {
  const data = normalizeTelemetry(raw);
  assert.equal(data.minutes, 3);
  assert.deepEqual(data.services[1].series.latency_p95_ms, [4, 5, 6]);
  assert.equal(data.services[1].slo.latency_p95_ms, 9);
  assert.equal(data.anomalies[0].start_minute, 2);
  assert.deepEqual(data.canarySteps.map((step) => step.minute), [40, 50]);
  assert.equal(normalizeTelemetry(null).minutes, 0);
});

test("pivotSeries respects the cursor but keeps every minute", () => {
  const rows = pivotSeries(normalizeTelemetry(raw), "latency_p95_ms", 1);
  assert.equal(rows.length, 3);
  assert.deepEqual(rows[1], { minute: 1, a: 2, b: 5 });
  assert.deepEqual(rows[2], { minute: 2, a: null, b: null });
});

test("detectAnomalies groups a spike and ignores quiet noise", () => {
  const quiet = Array.from({ length: 30 }, (_, index) => 100 + (index % 3));
  assert.deepEqual(detectAnomalies(quiet, { window: 10, z: 3 }), []);
  const spike = [...quiet.slice(0, 15), 600, 650, 620, ...quiet.slice(0, 5)];
  const found = detectAnomalies(spike, { window: 10, z: 3 });
  assert.equal(found.length, 1);
  assert.equal(found[0].start_minute, 15);
  assert.equal(found[0].end_minute, 17);
  assert.equal(found[0].peak_value, 650);
  const breach = detectAnomalies([1, 1, 1, 1, 9], { slo: 5 });
  assert.equal(breach.length, 1);
});

test("canaryAt, sloStatus and describeAnomaly read like the dashboard", () => {
  const steps = normalizeTelemetry(raw).canarySteps;
  assert.equal(canaryAt(steps, 30).percent, 0);
  assert.equal(canaryAt(steps, 45).percent, 5);
  assert.equal(canaryAt(steps, 59).percent, 50);
  assert.equal(sloStatus(900, 800).state, "breach");
  assert.equal(sloStatus(700, 800).state, "ok");
  assert.equal(sloStatus(700, null).state, "unknown");
  assert.equal(
    describeAnomaly({ service: "payment-db", metric: "latency_p95_ms", peak_value: 2140, baseline_mean: 310, z: 4.83, slo: 800 }),
    "payment-db p95 latency 2,140 ms, baseline 310 ms, z = 4.8 → breaks the SLO",
  );
});
