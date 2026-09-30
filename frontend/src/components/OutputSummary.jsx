const label = (key) =>
  ({
    rule_score: "Assessment score",
    winner: "Selected worker",
    utility: "Selection score",
    ranked_hypotheses: "Possible causes",
    telemetry_collected: "Telemetry collected",
    root_cause_confirmed: "Root cause confirmed",
    pass_fail: "Test outcome",
    code_change_generated: "Code generated",
    full_release_executed: "Full release executed",
    follow_up_ticket_created: "Follow-up ticket created",
    slo_check: "Service health check",
  })[key] || key.replaceAll("_", " ");
const hidden = new Set([
  "method",
  "provider",
  "model",
  "revision_status",
  "requires_llm_or_coding_tool",
]);
function Value({ value }) {
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (value === null) return <span>Not connected</span>;
  if (Array.isArray(value))
    return (
      <ul>
        {value.map((item, index) => (
          <li key={index}>
            {typeof item === "object" ? (
              <Value value={item} />
            ) : (
              String(item).replaceAll("_", " ")
            )}
          </li>
        ))}
      </ul>
    );
  if (typeof value === "object")
    return (
      <div className="output-nested">
        {Object.entries(value)
          .filter(([key]) => !hidden.has(key))
          .map(([key, item]) => (
            <div key={key}>
              <b>{label(key)}</b>
              <Value value={item} />
            </div>
          ))}
      </div>
    );
  return (
    <span>
      {typeof value === "number"
        ? Number(value.toFixed(3))
        : String(value).replaceAll("_", " ")}
    </span>
  );
}
export default function OutputSummary({ output, technical = true }) {
  if (!output || !Object.keys(output).length)
    return <p className="muted">This agent has not shared its result yet.</p>;
  return (
    <div className="output-summary">
      <dl>
        {Object.entries(output)
          .filter(([key]) => !hidden.has(key))
          .map(([key, value]) => (
            <div key={key}>
              <dt>{label(key)}</dt>
              <dd>
                <Value value={value} />
              </dd>
            </div>
          ))}
      </dl>
      {technical && (
        <details className="technical-details">
          <summary>View technical data</summary>
          <pre>{JSON.stringify(output, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
