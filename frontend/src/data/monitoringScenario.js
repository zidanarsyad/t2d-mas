// Offline monitoring scenario, used when GET /monitoring/telemetry is unavailable.
// Seeded and deterministic: the same scenario and seed always give the same hour of data.
// It returns the raw API shape, so it goes through normalizeTelemetry like live data.
import { DEFAULT_POLICY } from "../lib/policy.js";
import { detectAnomalies } from "../lib/telemetry.js";

/** Small seeded random generator (mulberry32). */
export function mulberry32(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

// Same services, baselines and SLOs as agents/tools.py.
const SERVICES = [
  { service: "api-gateway", node_id: "node-1", p95: 180, sloP95: 500 },
  { service: "order-service", node_id: "node-2", p95: 240, sloP95: 600 },
  { service: "payment-db", node_id: "node-3", p95: 310, sloP95: 800 },
];
const ERROR_BASE = 0.004;
const ERROR_SLO = 0.02;

export function makeScenario({ scenario = "flash_sale", seed = 42, minutes = 60, policy = DEFAULT_POLICY } = {}) {
  const flashSale = scenario === "flash_sale";
  const random = mulberry32(seed * 7919 + (flashSale ? 1 : 2));
  const jitter = (spread) => 1 + (random() * 2 - 1) * spread; // uniform noise, e.g. ±8%
  const anomalies = [];
  const services = SERVICES.map((item) => {
    const latency = [];
    const errors = [];
    const rps = [];
    for (let minute = 0; minute < minutes; minute += 1) {
      // The incident: payment-db slows down and fails more often from minute 20 to 32.
      const incident = flashSale && item.service === "payment-db" && minute >= 20 && minute <= 32;
      const surge = flashSale && minute >= 18 && minute <= 36;
      latency.push(Math.round(item.p95 * jitter(0.08) * (incident ? 6.9 : 1)));
      errors.push(Number((ERROR_BASE * jitter(0.08) + (incident ? 0.06 : 0)).toFixed(4)));
      rps.push(Math.round(420 * jitter(0.05) * (surge ? 3.2 : 1)));
    }
    [
      ["latency_p95_ms", latency, item.sloP95],
      ["error_rate", errors, ERROR_SLO],
    ].forEach(([metric, values, slo]) => {
      // The spread floor matches the backend's SLO baselines (std = 12% of the mean), so z values look alike.
      detectAnomalies(values, { window: 10, z: policy.monitoring.anomaly_z, slo, minStdRatio: 0.12 }).forEach((found, index) => {
        anomalies.push({ anomaly_id: `OFF-${scenario}-${seed}-${item.service}-${metric}-${index + 1}`, service: item.service, metric, slo, ...found });
      });
    });
    return {
      service: item.service,
      node_id: item.node_id,
      series: { latency_p95_ms: latency, error_rate: errors, rps },
      slo: { latency_p95_ms: item.sloP95, error_rate: ERROR_SLO },
    };
  });
  // After the fix: a 5% canary, then 25%, 50% and the full release once a person signs off.
  const canary = flashSale
    ? [
        { minute: 40, percent: policy.canary.percent, status: "healthy" },
        { minute: 46, percent: 25, status: "healthy" },
        { minute: 50, percent: 50, status: "healthy" },
        { minute: 54, percent: 100, status: "healthy", needs_human: true },
      ]
    : [];
  return { scenario, seed, simulated: true, step_seconds: 60, services, anomalies, canary_steps: canary };
}

/** The release behind the canary in this story (report: risk 0.28, below the canary limit). */
export const scenarioRelease = { ticket_id: "TCK-1042", risk_score: 0.28 };
