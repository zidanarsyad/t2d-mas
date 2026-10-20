import test from "node:test";
import assert from "node:assert/strict";
import { makeScenario, mulberry32 } from "./monitoringScenario.js";
import { normalizeTelemetry } from "../lib/telemetry.js";

test("the same scenario and seed always give the same data", () => {
  assert.deepEqual(makeScenario({ scenario: "flash_sale", seed: 42 }), makeScenario({ scenario: "flash_sale", seed: 42 }));
  assert.notDeepEqual(makeScenario({ seed: 42 }).services[0].series, makeScenario({ seed: 43 }).services[0].series);
  const random = mulberry32(7);
  const first = random();
  assert.ok(first >= 0 && first < 1);
  assert.equal(mulberry32(7)(), first);
});

test("the flash sale flags payment-db and the normal hour flags nothing", () => {
  const flash = normalizeTelemetry(makeScenario({ scenario: "flash_sale", seed: 42 }));
  assert.equal(flash.minutes, 60);
  assert.ok(flash.anomalies.length >= 1);
  assert.ok(flash.anomalies.every((anomaly) => anomaly.service === "payment-db"));
  const latency = flash.anomalies.find((anomaly) => anomaly.metric === "latency_p95_ms");
  assert.ok(latency.start_minute >= 20 && latency.end_minute <= 32);
  assert.ok(latency.peak_value > latency.slo);
  for (const seed of [1, 2, 3, 42, 99]) {
    assert.deepEqual(normalizeTelemetry(makeScenario({ scenario: "normal", seed })).anomalies, [], `seed ${seed}`);
  }
});

test("the canary only widens, and the full release needs a human", () => {
  const steps = normalizeTelemetry(makeScenario({ scenario: "flash_sale", seed: 42 })).canarySteps;
  assert.deepEqual(steps.map((step) => step.percent), [5, 25, 50, 100]);
  steps.slice(1).forEach((step, index) => {
    assert.ok(step.minute > steps[index].minute);
    assert.ok(step.percent > steps[index].percent);
  });
  assert.equal(steps.at(-1).needsHuman, true);
  assert.deepEqual(makeScenario({ scenario: "normal" }).canary_steps, []);
});
