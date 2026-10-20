import test from "node:test";
import assert from "node:assert/strict";
import {
  barWidth,
  experimentMetrics,
  formatBytes,
  formatDuration,
  formatNumber,
  formatRunLabel,
  formatTime,
  secondsSince,
  trendTone,
} from "./format.js";

test("trendTone separates direction from whether it is good", () => {
  assert.deepEqual(trendTone("+1.4", { goodDirection: "up" }), { direction: "up", tone: "good" });
  assert.deepEqual(trendTone("−18%", { goodDirection: "down" }), { direction: "down", tone: "good" });
  assert.deepEqual(trendTone("+0.6 pts", { goodDirection: "down" }), { direction: "up", tone: "bad" });
  assert.deepEqual(trendTone("-1.2 pts", { goodDirection: "up" }), { direction: "down", tone: "bad" });
  assert.deepEqual(trendTone("0"), { direction: "flat", tone: "neutral" });
});

test("barWidth is proportional with a minimum, and zero stays empty", () => {
  assert.equal(barWidth(50, 100), "50%");
  assert.equal(barWidth(84, 8190), "3%");
  assert.equal(barWidth(8190, 8190), "100%");
  assert.equal(barWidth(0, 100), "0%");
  assert.equal(barWidth(5, 0), "0%");
});

test("times are shown in WIB", () => {
  assert.equal(formatTime("2026-09-30T02:08:46.305626Z"), "09:08:46 WIB");
  assert.equal(formatTime("2026-09-30T17:30:00Z", { date: true, seconds: false }), "1 Oct 2026, 00:30 WIB");
  assert.equal(formatTime(null), "Time unavailable");
});

test("formatRunLabel replaces the raw run id", () => {
  const label = formatRunLabel({
    run_id: "20260930T020846305626",
    created_at_utc: "2026-09-30T02:08:46.305626Z",
    seeds: [42, 43, 44, 45, 46],
    tickets_per_seed: 100,
    dataset_version: "synthetic-eval-v1",
  });
  assert.equal(label, "30 Sep 2026, 09:08 WIB · 5 seeds × 100 tickets · synthetic-eval-v1");
  assert.match(formatRunLabel({ run_id: "20261020T030924214874" }), /^20 Oct 2026, 10:09 WIB/);
});

test("numbers, bytes and durations read like the report", () => {
  assert.equal(formatNumber(8190), "8,190");
  assert.equal(formatNumber(-1234.5, 1), "−1,234.5");
  assert.equal(formatBytes(84e6), "84 MB");
  assert.equal(formatBytes(1.5e6), "1.5 MB");
  assert.equal(formatBytes(120e6), "120 MB");
  assert.equal(formatBytes(8.19e9), "8.19 GB");
  assert.equal(formatBytes(1778), "1.78 KB");
  assert.equal(formatDuration(27), "27 s");
  assert.equal(formatDuration(655), "10 min 55 s");
  assert.equal(formatDuration(3 * 3600 + 42 * 60), "3 h 42 min");
});

test("experiment metrics have one unique label each", () => {
  const labels = experimentMetrics.map((metric) => metric.label);
  assert.equal(new Set(labels).size, labels.length);
  assert.ok(experimentMetrics.every((metric) => ["measured", "score", "simulated"].includes(metric.kind)));
  assert.equal(experimentMetrics.find((metric) => metric.key === "rollback_rate").kind, "simulated");
});

test("secondsSince never goes negative and tolerates microseconds", () => {
  const now = Date.parse("2026-10-20T07:01:20Z");
  assert.equal(secondsSince("2026-10-20T07:01:15.536655+00:00", now), 4.464);
  assert.equal(secondsSince("2026-10-20T07:01:30Z", now), 0);
  assert.equal(secondsSince(null, now), null);
});
