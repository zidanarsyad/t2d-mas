import { useEffect, useState } from "react";

/** Subscribe to FastAPI's SSE stream; EventSource handles automatic reconnects. */
export function useLiveEvents(onEvent) {
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [connectionEpoch, setConnectionEpoch] = useState(0);
  useEffect(() => {
    const source = new EventSource("/api/events");
    source.addEventListener("ready", () => {
      setConnected(true);
      setConnectionEpoch((value) => value + 1);
    });
    source.addEventListener("update", (event) => {
      setConnected(true);
      try {
        const data = JSON.parse(event.data);
        setLastUpdate(new Date());
        onEvent?.(data);
      } catch {
        /* Ignore malformed demo events without closing the stream. */
      }
    });
    source.onerror = () => setConnected(false);
    return () => source.close();
  }, [onEvent]);
  return { connected, lastUpdate, connectionEpoch };
}
