// The only file that talks to the backend over HTTP. Vite proxies /api/* to FastAPI.

export const API_BASE = "/api";
export const EVENTS_URL = `${API_BASE}/events`;

/** An HTTP error with its status; `offline` means the backend itself could not be reached. */
export class ApiError extends Error {
  constructor(message, { status = 0, offline = false } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.offline = offline;
  }
}

export async function request(path, { method = "GET", body, signal } = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      signal,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new ApiError("The backend is not reachable.", { offline: true });
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    // The dev proxy answers 5xx with no JSON body when the backend is not running.
    const offline = response.status >= 500 && !detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg).join(". ")
          : offline
            ? "The backend is not reachable."
            : `The request failed (HTTP ${response.status}).`;
    throw new ApiError(message, { status: response.status, offline });
  }
  return data ?? {};
}

/**
 * True when the dashboard should fall back to replay data: the backend is down, or an endpoint
 * from the new contract is missing (404) or not ready (503).
 */
export function isUnavailable(error) {
  return Boolean(error?.offline) || [404, 502, 503, 504].includes(error?.status);
}

const id = (value) => encodeURIComponent(value);
const query = (params) => new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null)).toString();

export const api = {
  health: (signal) => request("/health", { signal }),
  policy: (signal) => request("/policy", { signal }),
  tickets: (signal) => request("/sandbox/tickets", { signal }).then((data) => data.items || []),
  ticket: (ticketId) => request(`/sandbox/tickets/${id(ticketId)}`),
  createTicket: (payload) => request("/sandbox/tickets", { method: "POST", body: payload }),
  advance: (ticketId) => request(`/sandbox/tickets/${id(ticketId)}/advance`, { method: "POST" }),
  review: (ticketId, payload) => request(`/sandbox/tickets/${id(ticketId)}/review`, { method: "POST", body: payload }),
  messages: (limit = 500) => request(`/messages/history?${query({ limit })}`).then((data) => data.items || []),
  feedbackInbox: ({ seed = 42, count = 8, scenario = "all" } = {}) => request(`/feedback/inbox?${query({ seed, count, scenario })}`),
  telemetry: ({ scenario = "flash_sale", seed = 42 } = {}) => request(`/monitoring/telemetry?${query({ scenario, seed })}`),
  ticketFromAnomaly: (anomalyId) => request(`/monitoring/anomalies/${id(anomalyId)}/ticket`, { method: "POST" }),
  migrate: (nodeNumber, signal) => request(`/demo/migrate/${id(nodeNumber)}`, { method: "POST", signal }),
  experiments: () => request("/experiments").then((data) => data.runs || []),
  evalHistory: ({ runId, severity, seed = "all", limit = 50 } = {}) => request(`/history?${query({ run_id: runId, severity, seed, limit })}`),
  ticketHistory: (limit = 50) => request(`/ticket-history?${query({ limit })}`).then((data) => data.items || []),
};
