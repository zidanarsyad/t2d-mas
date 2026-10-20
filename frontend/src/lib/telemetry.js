// Telemetry helpers for the Monitoring view (shape of GET /monitoring/telemetry).
import { formatNumber, formatPercent } from "./format.js";

export const METRICS = [
  { id: "latency_p95_ms", label: "p95 latency", term: "p95", unit: "ms", format: (v) => `${formatNumber(v)} ms` },
  { id: "error_rate", label: "Error rate", term: "error-rate", unit: "%", format: (v) => formatPercent(v, 1) },
  { id: "rps", label: "Requests per second", term: null, unit: "rps", format: (v) => `${formatNumber(v)} rps` },
];

export const metricInfo = (id) => METRICS.find((metric) => metric.id === id) || METRICS[0];

const list = (value) => (Array.isArray(value) ? value.map((item) => (item === null || item === undefined ? null : Number(item))) : []);
const num = (value) => (value === null || value === undefined || !Number.isFinite(Number(value)) ? null : Number(value));

/** One predictable shape for live or offline telemetry; older field names are accepted too. */
export function normalizeTelemetry(raw) {
  const value = raw && typeof raw === "object" ? raw : {};
  const services = (Array.isArray(value.services) ? value.services : []).map((item) => {
    const series = item?.series || {};
    return {
      service: item?.service || item?.name || "service",
      nodeId: item?.node_id || null,
      series: {
        latency_p95_ms: list(series.latency_p95_ms ?? series.p95 ?? series.latency),
        error_rate: list(series.error_rate ?? series.errors),
        rps: list(series.rps ?? series.requests_per_second),
      },
      slo: {
        latency_p95_ms: num(item?.slo?.latency_p95_ms ?? item?.slo?.p95),
        error_rate: num(item?.slo?.error_rate),
      },
    };
  });
  const minutes = services.reduce((most, item) => Math.max(most, ...Object.values(item.series).map((points) => points.length)), 0);
  const anomalies = (Array.isArray(value.anomalies) ? value.anomalies : []).map((item, index) => ({
    anomaly_id: item?.anomaly_id || `anomaly-${index + 1}`,
    service: item?.service || "service",
    metric: item?.metric || "latency_p95_ms",
    start_minute: num(item?.start_minute) ?? num(item?.peak_minute) ?? 0,
    end_minute: num(item?.end_minute) ?? num(item?.peak_minute) ?? num(item?.start_minute) ?? 0,
    peak_minute: num(item?.peak_minute) ?? num(item?.start_minute) ?? 0,
    peak_value: num(item?.peak_value ?? item?.value),
    baseline_mean: num(item?.baseline_mean),
    slo: num(item?.slo),
    z: num(item?.z),
  }));
  const canarySteps = (Array.isArray(value.canary_steps) ? value.canary_steps : [])
    .map((step) => ({
      minute: num(step?.minute) ?? 0,
      percent: num(step?.percent) ?? 0,
      status: step?.status || "healthy",
      needsHuman: Boolean(step?.needs_human ?? step?.needsHuman),
    }))
    .sort((a, b) => a.minute - b.minute);
  return {
    scenario: value.scenario || "flash_sale",
    seed: value.seed ?? null,
    simulated: value.simulated !== false,
    stepSeconds: num(value.step_seconds) || 60,
    minutes,
    services,
    anomalies: anomalies.sort((a, b) => a.start_minute - b.start_minute),
    canarySteps,
  };
}

/**
 * Chart rows {minute, [service]: value}. Minutes after the cursor are null, so the x axis
 * keeps its full length while the lines grow.
 */
export function pivotSeries(telemetry, metric, cursor = Infinity) {
  const rows = [];
  for (let minute = 0; minute < (telemetry?.minutes || 0); minute += 1) {
    const row = { minute };
    (telemetry.services || []).forEach((item) => {
      const value = item.series[metric]?.[minute];
      row[item.service] = minute <= cursor && value !== undefined ? value : null;
    });
    rows.push(row);
  }
  return rows;
}

const mean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;
const deviation = (values) => {
  const average = mean(values);
  return Math.sqrt(values.reduce((sum, value) => sum + (value - average) ** 2, 0) / values.length);
};

/**
 * Flag points whose z-score against the recent normal points reaches `z`, or that break the SLO.
 * Flagged points do not enter the baseline, so a long spike stays visible. Consecutive flagged
 * minutes become one anomaly. `minStdRatio` stops a very quiet window from inflating z.
 */
export function detectAnomalies(values, { window = 10, z = 3, slo = null, minStdRatio = 0.05 } = {}) {
  const baseline = [];
  const flagged = [];
  (values || []).forEach((value, minute) => {
    if (value === null || value === undefined) return;
    if (baseline.length >= 3) {
      const recent = baseline.slice(-window);
      const average = mean(recent);
      const spread = Math.max(deviation(recent), Math.abs(average) * minStdRatio, 1e-9);
      const score = (value - average) / spread;
      if (score >= z || (slo !== null && value > slo)) {
        flagged.push({ minute, value, z: score, mean: average });
        return;
      }
    }
    baseline.push(value);
  });
  const groups = [];
  flagged.forEach((point) => {
    const last = groups.at(-1);
    if (last && point.minute === last.end_minute + 1) {
      last.end_minute = point.minute;
      if (point.value > last.peak_value) Object.assign(last, { peak_minute: point.minute, peak_value: point.value, z: point.z });
    } else {
      groups.push({ start_minute: point.minute, end_minute: point.minute, peak_minute: point.minute, peak_value: point.value, baseline_mean: point.mean, z: point.z });
    }
  });
  return groups.map((group) => ({ ...group, z: Number(group.z.toFixed(1)), baseline_mean: Number(group.baseline_mean.toFixed(4)) }));
}

/** The canary step in force at a minute: 0% before the first step. */
export function canaryAt(steps, minute) {
  const reached = (steps || []).filter((step) => step.minute <= minute);
  return reached.at(-1) || { minute: 0, percent: 0, status: "not_started", needsHuman: false };
}

export function sloStatus(value, slo) {
  if (value === null || value === undefined || slo === null || slo === undefined) return { state: "unknown", label: "No SLO" };
  return Number(value) > Number(slo) ? { state: "breach", label: "Breaks SLO" } : { state: "ok", label: "Within SLO" };
}

/** "payment-db p95 latency 2,140 ms, baseline 310 ms, z = 4.8 → breaks the SLO" */
export function describeAnomaly(anomaly) {
  if (!anomaly) return "";
  const metric = metricInfo(anomaly.metric);
  const breaks = anomaly.slo !== null && anomaly.peak_value > anomaly.slo ? " → breaks the SLO" : "";
  return `${anomaly.service} ${metric.label.toLowerCase()} ${metric.format(anomaly.peak_value)}, baseline ${metric.format(anomaly.baseline_mean)}, z = ${formatNumber(anomaly.z, 1)}${breaks}`;
}
