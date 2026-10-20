import { useEffect, useRef, useState } from "react";
import { EVENTS_URL } from "../api";

/**
 * Subscribe to the backend's server-sent events. EventSource retries network errors itself,
 * but it gives up on an HTTP error (the dev proxy answers 500 while the backend is stopped),
 * so we reopen the stream ourselves with a growing delay.
 */
export function useLiveEvents(onEvent) {
  const handler = useRef(onEvent);
  const [connected, setConnected] = useState(false);
  const [connectionEpoch, setConnectionEpoch] = useState(0);

  useEffect(() => {
    handler.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (typeof EventSource === "undefined") return undefined;
    let source = null;
    let retryTimer = null;
    let delay = 3000;
    let stopped = false;

    const open = () => {
      source = new EventSource(EVENTS_URL);
      source.addEventListener("ready", () => {
        delay = 3000;
        setConnected(true);
        setConnectionEpoch((value) => value + 1);
      });
      source.addEventListener("update", (event) => {
        try {
          handler.current?.(JSON.parse(event.data));
        } catch {
          /* Ignore a malformed event without closing the stream. */
        }
      });
      source.onerror = () => {
        setConnected(false);
        if (source.readyState === EventSource.CLOSED && !stopped) {
          retryTimer = window.setTimeout(open, delay);
          delay = Math.min(delay * 2, 30000);
        }
      };
    };

    open();
    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      source?.close();
    };
  }, []);

  return { connected, connectionEpoch };
}
