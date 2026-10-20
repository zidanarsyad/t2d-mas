// A readable view of an agent's output object, with the raw JSON one click away.
import { formatNumber } from "../lib/format.js";

const LABELS = {
  rule_score: "Rule score",
  winner: "Selected worker",
  utility: "Utility score",
  ranked_hypotheses: "Possible causes",
  root_cause_confirmed: "Root cause confirmed",
  pass_fail: "Test outcome",
  code_change_generated: "Code generated",
  full_release_executed: "Full release executed",
  follow_up_ticket_created: "Follow-up ticket created",
  normalized_title: "Ticket title",
  grouped_reports: "Reports grouped",
  linked_duplicates: "Duplicates linked",
  risk_score: "Release risk score",
  napfd: "NAPFD",
  sla_due: "SLA due",
  sla_hours: "SLA (hours)",
};

// Envelope fields are shown elsewhere (StageDetails), so they are hidden here.
const HIDDEN = new Set([
  "stage", "agent", "family", "mobility", "execution_mode", "simulated", "simulation_note", "seed", "revision",
  "summary", "components", "tools_used", "decisions", "reviewer_guidance", "method", "provider", "model",
  "revision_status", "requires_llm_or_coding_tool", "time_label",
]);

const label = (key) => LABELS[key] || key.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());

function Value({ value }) {
  if (value === null || value === undefined) return <span className="muted">Not recorded</span>;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (typeof value === "number") return <span>{Number.isInteger(value) ? formatNumber(value) : formatNumber(value, 3)}</span>;
  if (Array.isArray(value)) {
    if (!value.length) return <span className="muted">None</span>;
    return (
      <ul className="output-list">
        {value.map((item, index) => (
          <li key={index}>{typeof item === "object" && item !== null ? <Value value={item} /> : String(item).replaceAll("_", " ")}</li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") {
    return (
      <dl className="output-nested">
        {Object.entries(value)
          .filter(([key]) => !HIDDEN.has(key))
          .map(([key, item]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>
                <Value value={item} />
              </dd>
            </div>
          ))}
      </dl>
    );
  }
  return <span>{String(value).replaceAll("_", " ")}</span>;
}

export default function OutputSummary({ output, technical = true }) {
  const entries = output && typeof output === "object" ? Object.entries(output).filter(([key]) => !HIDDEN.has(key)) : [];
  if (!output || typeof output !== "object") return <p className="muted">This agent has not shared a result yet.</p>;
  return (
    <div className="output-summary">
      {entries.length > 0 && (
        <dl className="output-grid">
          {entries.map(([key, value]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>
                <Value value={value} />
              </dd>
            </div>
          ))}
        </dl>
      )}
      {technical && (
        <details className="details">
          <summary>Show the raw data</summary>
          <pre className="code-block">{JSON.stringify(output, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
