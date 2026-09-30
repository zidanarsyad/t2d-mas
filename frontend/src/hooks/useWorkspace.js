import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "../api";
import { mergeMessages } from "../workflow";
import { useLiveEvents } from "./useLiveEvents";

export function useWorkspace() {
  const [records, setRecords] = useState([]);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const upsert = useCallback((record) => {
    generation.current++;
    setRecords((rows) => [
      record,
      ...rows.filter((item) => item.ticket_id !== record.ticket_id),
    ]);
  }, []);
  const refresh = useCallback(async () => {
    const version = ++generation.current;
    try {
      const data = await request("/sandbox/tickets");
      if (version === generation.current) {
        setRecords(data.items || []);
        setError("");
      }
    } catch (err) {
      if (version === generation.current) setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);
  const onEvent = useCallback(
    (event) => {
      if (event.type === "message.published")
        setMessages((rows) => mergeMessages(rows, [event]));
      else if (
        [
          "ticket.started",
          "pipeline.advanced",
          "pipeline.completed",
          "approval.requested",
          "approval.resolved",
        ].includes(event.type)
      )
        refresh();
    },
    [refresh],
  );
  const { connected, lastUpdate, connectionEpoch } = useLiveEvents(onEvent);
  useEffect(() => {
    refresh();
  }, [refresh, connectionEpoch]);
  useEffect(() => {
    let active = true;
    request("/messages/history?limit=500")
      .then((data) => {
        if (active)
          setMessages((rows) => mergeMessages(rows, data.items || []));
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [connectionEpoch]);
  return {
    records,
    messages,
    connected,
    lastUpdate,
    loading,
    error,
    refresh,
    upsert,
  };
}
