import { ArrowRight, Gavel, MessageSquareText, ShieldAlert, Sparkles, Zap } from "lucide-react";
import { formatTime } from "../lib/format.js";
import { shortAgentName } from "../lib/workflow.js";

const KIND = {
  message: { icon: MessageSquareText, label: "Message" },
  output: { icon: Sparkles, label: "Agent result" },
  gate: { icon: ShieldAlert, label: "Policy check" },
  decision: { icon: Gavel, label: "Human decision" },
  action: { icon: Zap, label: "Action" },
  event: { icon: MessageSquareText, label: "Event" },
};

/** The decision trace as a list. Selecting a row seeks the animated flow to that step. */
export default function TraceTimeline({ entries, selectedIndex, onSelect }) {
  if (!entries.length) return null;
  return (
    <ol className="trace-list">
      {entries.map((entry, index) => {
        const kind = KIND[entry.kind] || KIND.event;
        const selected = index === selectedIndex;
        // Rows are buttons only when selecting one does something (seeking the flow).
        const Row = onSelect ? "button" : "div";
        const rowProps = onSelect ? { type: "button", onClick: () => onSelect(index), "aria-current": selected ? "step" : undefined } : {};
        return (
          <li key={entry.id} className={`kind-${entry.kind}`}>
            <Row className={`trace-button ${selected ? "is-selected" : ""}`} {...rowProps}>
              <span className="trace-icon" aria-hidden="true">
                <kind.icon size={15} />
              </span>
              <span className="trace-text">
                <span className="trace-top">
                  <b>{entry.title}</b>
                  <time>{entry.at ? formatTime(entry.at) : "—"}</time>
                </span>
                <span className="trace-route">
                  {shortAgentName(entry.actor)}
                  {entry.receivers.length > 0 && (
                    <>
                      <ArrowRight size={12} aria-hidden="true" />
                      {entry.receivers.map(shortAgentName).join(", ")}
                    </>
                  )}
                  {entry.performative && <code className="raw-name">{entry.performative}</code>}
                  <span className="visually-hidden">({kind.label})</span>
                </span>
                {entry.detail && <span className="trace-detail">{entry.detail}</span>}
              </span>
            </Row>
          </li>
        );
      })}
    </ol>
  );
}
