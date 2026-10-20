import { useCallback, useEffect, useState } from "react";
import { useReducedMotion } from "./useReducedMotion";

/**
 * Step through a list (frames, minutes...) like a video player.
 * One timeout per step; each step may set its own `durationMs`, otherwise `baseMs` is used.
 * It never autoplays with reduced motion and pauses when the browser tab is hidden.
 */
export function useStepPlayer(steps, { autoPlay = false, baseMs = 1000 } = {}) {
  const reduced = useReducedMotion();
  const count = steps?.length || 0;
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(() => autoPlay && !reduced);
  const [speed, setSpeed] = useState(1);

  // Keep the index valid when the list changes length.
  useEffect(() => {
    setIndex((value) => Math.min(value, Math.max(0, count - 1)));
  }, [count]);

  useEffect(() => {
    if (reduced && autoPlay) setPlaying(false);
  }, [reduced, autoPlay]);

  useEffect(() => {
    if (!playing || count === 0) return undefined;
    if (index >= count - 1) {
      setPlaying(false);
      return undefined;
    }
    const duration = (steps[index]?.durationMs ?? baseMs) / speed;
    const timer = window.setTimeout(() => setIndex((value) => Math.min(value + 1, count - 1)), duration);
    return () => window.clearTimeout(timer);
  }, [playing, index, speed, count, steps, baseMs]);

  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) setPlaying(false);
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  const play = useCallback(() => {
    setIndex((value) => (value >= count - 1 ? 0 : value));
    setPlaying(true);
  }, [count]);
  const pause = useCallback(() => setPlaying(false), []);
  const toggle = useCallback(() => (playing ? pause() : play()), [playing, pause, play]);
  const seek = useCallback((value) => setIndex(Math.max(0, Math.min(count - 1, Number(value) || 0))), [count]);
  const next = useCallback(() => {
    setPlaying(false);
    setIndex((value) => Math.min(value + 1, Math.max(0, count - 1)));
  }, [count]);
  const prev = useCallback(() => {
    setPlaying(false);
    setIndex((value) => Math.max(value - 1, 0));
  }, []);
  const restart = useCallback(() => {
    setIndex(0);
    setPlaying(!reduced);
  }, [reduced]);

  return { index, step: steps?.[index], count, playing, speed, reduced, play, pause, toggle, next, prev, seek, restart, setSpeed };
}
