import { useId, useRef, useState } from "react";
import { glossaryEntry } from "../data/glossary.js";

/**
 * A glossary word with a tooltip. It opens on hover and focus, a tap or click toggles it,
 * and Esc closes it. The text is also linked with aria-describedby for screen readers.
 */
export default function Term({ id, children }) {
  const entry = glossaryEntry(id);
  const tipId = useId();
  const [open, setOpen] = useState(false);
  // The click that focuses the term (mouse or tap) should not close what the focus opened.
  const focusedByPointer = useRef(false);
  if (!entry) return children ?? null;
  return (
    <span className="term-wrap" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        className="term"
        aria-describedby={tipId}
        aria-expanded={open}
        onFocus={() => {
          focusedByPointer.current = true;
          setOpen(true);
        }}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => {
          focusedByPointer.current = false;
          if (event.key === "Escape") setOpen(false);
        }}
        onClick={() => {
          if (focusedByPointer.current) {
            focusedByPointer.current = false;
            setOpen(true);
            return;
          }
          setOpen((value) => !value);
        }}
      >
        {children || entry.term}
      </button>
      <span role="tooltip" id={tipId} className="term-tip" hidden={!open}>
        <b>{entry.term}.</b> {entry.short}
      </span>
    </span>
  );
}
