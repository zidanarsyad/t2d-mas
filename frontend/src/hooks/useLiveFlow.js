import { useEffect, useMemo, useRef, useState } from "react";
import { enqueueFrames, frameFromSnapshot, framesFromMessages } from "../lib/flow.js";
import { useReducedMotion } from "./useReducedMotion";

const STEP_MS = 900;
const HOLD_MS = 1400;

/**
 * Live mode for the pipeline flow. Messages that already exist when a ticket is opened count
 * as seen; each new message for the ticket becomes a frame in a small queue (at most 8), shown
 * one every 900 ms. When nothing is queued, the flow shows the ticket snapshot.
 */
export function useLiveFlow(record, messages, policy) {
  const reduced = useReducedMotion();
  const ticketId = record?.ticket_id || null;
  const snapshotFrame = useMemo(() => (record ? frameFromSnapshot(record, policy) : null), [record, policy]);
  const seen = useRef(new Set());
  const [queue, setQueue] = useState([]);
  const [current, setCurrent] = useState(null);
  const shown = current || snapshotFrame;
  const shownRef = useRef(shown);
  const messagesRef = useRef(messages);

  // Keep the latest values for the effects below (they run in this order after each render).
  useEffect(() => {
    shownRef.current = shown;
    messagesRef.current = messages;
  });

  // A different ticket: everything already recorded for it counts as seen.
  useEffect(() => {
    seen.current = new Set((messagesRef.current || []).filter((item) => item.correlation_id === ticketId).map((item) => item.message_id));
    setQueue([]);
    setCurrent(null);
  }, [ticketId]);

  useEffect(() => {
    if (!ticketId) return;
    const fresh = (messages || []).filter((item) => item.correlation_id === ticketId && !seen.current.has(item.message_id));
    if (!fresh.length) return;
    fresh.forEach((item) => seen.current.add(item.message_id));
    const frames = framesFromMessages(fresh, { policy, startStages: shownRef.current?.stages, prefix: `live-${ticketId}`, clock: true });
    setQueue((items) => enqueueFrames(items, frames, 8));
  }, [messages, ticketId, policy]);

  // Show the next queued frame; with reduced motion there is no waiting between frames.
  useEffect(() => {
    if (!queue.length) return undefined;
    const timer = window.setTimeout(
      () => {
        setCurrent(queue[0]);
        setQueue((items) => items.slice(1));
      },
      current && !reduced ? STEP_MS : 0,
    );
    return () => window.clearTimeout(timer);
  }, [queue, current, reduced]);

  // After the last queued frame, hold it briefly, then return to the snapshot.
  useEffect(() => {
    if (queue.length || !current) return undefined;
    const timer = window.setTimeout(() => setCurrent(null), reduced ? 0 : HOLD_MS);
    return () => window.clearTimeout(timer);
  }, [queue, current, reduced]);

  return { frame: shown, animating: Boolean(current), queued: queue.length };
}
