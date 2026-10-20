import { useEffect, useState } from "react";

/** The current time, refreshed every `intervalMs` (for "time in stage" and "waiting for" labels). */
export function useNow(intervalMs = 30000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}
