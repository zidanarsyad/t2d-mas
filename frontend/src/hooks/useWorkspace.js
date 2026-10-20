import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { DEFAULT_POLICY, normalizePolicy } from "../lib/policy.js";
import { isWaiting, mergeMessages, normalizeSnapshot } from "../lib/workflow.js";
import { useLiveEvents } from "./useLiveEvents";

// Events after which the ticket list is fetched again (debounced, so a burst costs one request).
const REFRESH_ON = new Set([
  "ticket.started",
  "pipeline.advanced",
  "pipeline.completed",
  "approval.requested",
  "approval.resolved",
  "review.clarification_requested",
  "ticket.follow_up",
  "duplicate.linked",
  "action.executed",
  "action.blocked",
]);

/**
 * Shared app state: tickets, agent messages, the policy, backend health and the live/replay mode.
 * Pages that animate (flow, trip, monitoring) listen to raw events through `subscribe`.
 */
export function useWorkspace() {
  const [records, setRecords] = useState([]);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [policy, setPolicy] = useState(DEFAULT_POLICY);
  const [health, setHealth] = useState(null);
  const listeners = useRef(new Set());
  const generation = useRef(0);
  const refreshTimer = useRef(null);

  const subscribe = useCallback((listener) => {
    listeners.current.add(listener);
    return () => listeners.current.delete(listener);
  }, []);

  const upsert = useCallback((raw) => {
    const record = normalizeSnapshot(raw);
    generation.current += 1;
    setRecords((rows) => [record, ...rows.filter((item) => item.ticket_id !== record.ticket_id)]);
    return record;
  }, []);

  const refresh = useCallback(async () => {
    const version = ++generation.current;
    try {
      const items = await api.tickets();
      if (version === generation.current) {
        setRecords(items.map(normalizeSnapshot));
        setError("");
      }
    } catch (err) {
      if (version === generation.current) setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshSoon = useCallback(() => {
    window.clearTimeout(refreshTimer.current);
    refreshTimer.current = window.setTimeout(refresh, 150);
  }, [refresh]);

  const onEvent = useCallback(
    (event) => {
      if (event?.type === "message.published") setMessages((rows) => mergeMessages(rows, [event]));
      else if (REFRESH_ON.has(event?.type)) refreshSoon();
      listeners.current.forEach((listener) => listener(event));
    },
    [refreshSoon],
  );

  const { connected, connectionEpoch } = useLiveEvents(onEvent);

  // Tickets, message history, policy and health are (re)loaded whenever the stream (re)connects;
  // losing the stream re-checks health, so the Live/Replay badge stays honest.
  useEffect(() => {
    refresh();
  }, [refresh, connectionEpoch]);

  useEffect(() => {
    let active = true;
    api.messages(500).then((items) => active && setMessages((rows) => mergeMessages(rows, items))).catch(() => {});
    api.policy().then((data) => active && setPolicy(normalizePolicy(data))).catch(() => active && setPolicy(DEFAULT_POLICY));
    api.health().then((data) => active && setHealth(data)).catch(() => active && setHealth(null));
    return () => {
      active = false;
    };
  }, [connectionEpoch, connected]);

  useEffect(() => () => window.clearTimeout(refreshTimer.current), []);

  const mode = connected || health?.status === "ok" ? "live" : "replay";
  const pendingCount = useMemo(() => records.filter(isWaiting).length, [records]);

  return { records, messages, connected, loading, error, refresh, upsert, policy, health, mode, pendingCount, subscribe };
}
