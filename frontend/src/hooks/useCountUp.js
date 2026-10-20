import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "./useReducedMotion";

/** Animate a number towards `target` with requestAnimationFrame; jump straight there with reduced motion. */
export function useCountUp(target, { durationMs = 900 } = {}) {
  const reduced = useReducedMotion();
  const [value, setValue] = useState(target);
  const from = useRef(target);

  useEffect(() => {
    const start = from.current;
    if (reduced || durationMs <= 0 || start === target || !Number.isFinite(target)) {
      from.current = target;
      setValue(target);
      return undefined;
    }
    let frame = 0;
    const began = performance.now();
    const tick = (now) => {
      const progress = Math.min(1, (now - began) / durationMs);
      const eased = 1 - (1 - progress) ** 3;
      const next = start + (target - start) * eased;
      from.current = next;
      setValue(next);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs, reduced]);

  return value;
}
