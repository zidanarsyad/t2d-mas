// Formatting helpers. Times are shown in Jakarta time (WIB = UTC+7, no daylight saving),
// computed by hand so the output never depends on the browser's locale data.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WIB_OFFSET_MS = 7 * 60 * 60 * 1000;
const pad = (value) => String(value).padStart(2, "0");

/** Parse an ISO time (any number of fraction digits) or a Date; null when invalid. */
export function toDate(value) {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  // Some backends write microseconds; JS dates only need milliseconds.
  const text = String(value).replace(/(\.\d{3})\d+/, "$1");
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

function wibParts(value) {
  const date = toDate(value);
  if (!date) return null;
  const shifted = new Date(date.getTime() + WIB_OFFSET_MS);
  return {
    year: shifted.getUTCFullYear(),
    month: MONTHS[shifted.getUTCMonth()],
    day: shifted.getUTCDate(),
    time: `${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}`,
    seconds: pad(shifted.getUTCSeconds()),
  };
}

/** "09:08:46 WIB", or "30 Sep 2026, 09:08 WIB" with `{ date: true, seconds: false }`. */
export function formatTime(value, { date = false, seconds = true, zone = true } = {}) {
  const parts = wibParts(value);
  if (!parts) return "Time unavailable";
  const clock = seconds ? `${parts.time}:${parts.seconds}` : parts.time;
  const text = date ? `${parts.day} ${parts.month} ${parts.year}, ${clock}` : clock;
  return zone ? `${text} WIB` : text;
}

/** Group digits with commas without relying on locale data: 8190 -> "8,190". */
export function formatNumber(value, digits = 0) {
  const number = Number(value);
  if (value === null || value === undefined || value === "" || !Number.isFinite(number)) return "—";
  const [whole, fraction] = Math.abs(number).toFixed(digits).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${number < 0 ? "−" : ""}${grouped}${fraction ? `.${fraction}` : ""}`;
}

export function formatPercent(ratio, digits = 1) {
  return Number.isFinite(Number(ratio)) && ratio !== null ? `${formatNumber(Number(ratio) * 100, digits)}%` : "—";
}

/** A duration in seconds: "27 s", "10 min 55 s", "3 h 42 min", "2 d 4 h". */
export function formatDuration(seconds) {
  const value = Number(seconds);
  if (seconds === null || seconds === undefined || !Number.isFinite(value) || value < 0) return "—";
  if (value < 60) return `${Math.round(value)} s`;
  if (value < 3600) {
    const minutes = Math.floor(value / 60);
    const rest = Math.round(value - minutes * 60);
    return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
  }
  if (value < 86400) {
    const hours = Math.floor(value / 3600);
    const minutes = Math.round((value - hours * 3600) / 60);
    return minutes ? `${hours} h ${minutes} min` : `${hours} h`;
  }
  const days = Math.floor(value / 86400);
  const hours = Math.round((value - days * 86400) / 3600);
  return hours ? `${days} d ${hours} h` : `${days} d`;
}

/**
 * Seconds from `value` until `now`, never negative: a clock that ticks only every few seconds
 * may be slightly older than a timestamp the server just wrote. Null when there is no time.
 */
export function secondsSince(value, now = Date.now()) {
  const date = toDate(value);
  return date ? Math.max(0, (now - date.getTime()) / 1000) : null;
}

/** Bytes in decimal units (1 MB = 1,000,000 bytes, as in the report). */
export function formatBytes(bytes) {
  const value = Number(bytes);
  if (bytes === null || bytes === undefined || !Number.isFinite(value)) return "—";
  const units = [
    [1e9, "GB"],
    [1e6, "MB"],
    [1e3, "KB"],
  ];
  for (const [size, unit] of units) {
    if (Math.abs(value) >= size) {
      const scaled = value / size;
      // Two decimals for small values, fewer for big ones, and no trailing zeros ("84 MB").
      let text = formatNumber(scaled, scaled < 10 ? 2 : scaled < 100 ? 1 : 0);
      if (text.includes(".")) text = text.replace(/0+$/, "").replace(/\.$/, "");
      return `${text} ${unit}`;
    }
  }
  return `${formatNumber(value)} B`;
}

/** Megabytes as the report writes them: "8,190 MB". */
export function formatMB(mb) {
  return `${formatNumber(mb, Number(mb) % 1 ? 1 : 0)} MB`;
}

/** "T+04:30" from seconds since the start of a story. */
export function formatOffset(seconds) {
  const value = Math.max(0, Math.round(Number(seconds) || 0));
  return `T+${pad(Math.floor(value / 60))}:${pad(value % 60)}`;
}

/** Time of an evaluation run from its metadata, or from a run id like 20260930T020846305626. */
export function runTime(run) {
  const fromMeta = toDate(run?.created_at_utc);
  if (fromMeta) return fromMeta;
  const match = String(run?.run_id || "").match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/);
  return match ? new Date(Date.UTC(+match[1], +match[2] - 1, +match[3], +match[4], +match[5], +match[6])) : null;
}

/** "30 Sep 2026, 09:08 WIB · 5 seeds × 100 tickets · synthetic-eval-v1" instead of a raw run id. */
export function formatRunLabel(run) {
  const time = runTime(run);
  const parts = [time ? formatTime(time, { date: true, seconds: false }) : run?.run_id || "Saved run"];
  const seeds = Array.isArray(run?.seeds) ? run.seeds.length : 0;
  if (seeds && run?.tickets_per_seed) parts.push(`${seeds} ${seeds === 1 ? "seed" : "seeds"} × ${run.tickets_per_seed} tickets`);
  if (run?.dataset_version) parts.push(run.dataset_version);
  return parts.join(" · ");
}

/**
 * Direction and tone of a change such as "+1.4", "−18%" or "-1.2 pts".
 * `goodDirection` says which way is an improvement for this metric.
 */
export function trendTone(change, { goodDirection = "down" } = {}) {
  const number = typeof change === "number" ? change : Number(String(change ?? "").replace("−", "-").replace(/[^0-9.+-]/g, ""));
  if (!Number.isFinite(number) || number === 0) return { direction: "flat", tone: "neutral" };
  const direction = number > 0 ? "up" : "down";
  return { direction, tone: direction === goodDirection ? "good" : "bad" };
}

/** Bar width as a CSS percentage: proportional to `max`, never thinner than `minPercent` unless zero. */
export function barWidth(value, max, minPercent = 3) {
  const number = Number(value);
  const top = Number(max);
  if (!Number.isFinite(number) || number <= 0 || !Number.isFinite(top) || top <= 0) return "0%";
  const percent = Math.min(100, Math.max(minPercent, (number / top) * 100));
  return `${Number(percent.toFixed(1))}%`;
}

/** Clamp a number into [low, high]. */
export const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

/**
 * The one list of evaluation metrics, with one name each (used in every table and card).
 * `kind` says whether a number was measured on the run machine, scored, or simulated.
 */
export const experimentMetrics = [
  { key: "wall_time_mean_s", label: "Time per ticket", kind: "measured", better: "lower", format: (v) => `${formatNumber(Number(v) * 1000, 3)} ms` },
  { key: "macro_f1_severity", label: "Severity accuracy · Macro-F1", kind: "score", better: "higher", format: (v) => formatNumber(v, 2) },
  { key: "mean_recall_at_5", label: "Duplicates found · Recall@5", kind: "score", better: "higher", format: (v) => formatPercent(v, 1) },
  { key: "napfd_mean", label: "Failing tests found early · NAPFD", kind: "score", better: "higher", format: (v) => formatNumber(v, 2) },
  { key: "lead_time_hours_mean", label: "Lead time", kind: "simulated", better: "lower", format: (v) => `${formatNumber(v, 2)} h` },
  { key: "rollback_rate", label: "Rollback rate", kind: "simulated", better: "lower", format: (v) => formatPercent(v, 1) },
  { key: "network_bytes_mean", label: "Data sent per ticket", kind: "measured", better: "lower", format: (v) => formatBytes(v) },
];
