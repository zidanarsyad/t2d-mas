import { CircleCheck, CircleX } from "lucide-react";
import { gateEvidence } from "../lib/policy.js";
import Term from "./Term";

/** Value-vs-limit rows for the pending gate, with icon + word for pass and fail. */
export default function GateEvidence({ record, policy }) {
  const evidence = gateEvidence(record, policy);
  return (
    <div className="gate-evidence">
      {evidence.rows.length > 0 && (
        <table className="table compact">
          <thead>
            <tr>
              <th scope="col">Check</th>
              <th scope="col">Value</th>
              <th scope="col">Limit</th>
              <th scope="col">Result</th>
            </tr>
          </thead>
          <tbody>
            {evidence.rows.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.term ? <Term id={row.term}>{row.label}</Term> : row.label}</th>
                <td>{row.value}</td>
                <td>{row.limit}</td>
                <td>
                  {row.ok === true && (
                    <span className="text-ok">
                      <CircleCheck size={14} aria-hidden="true" /> passes
                    </span>
                  )}
                  {row.ok === false && (
                    <span className="text-bad">
                      <CircleX size={14} aria-hidden="true" /> fails
                    </span>
                  )}
                  {row.ok === null && <span className="muted">for information</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {evidence.note && <p className="muted">{evidence.note}</p>}
      {record.pending_gate?.reason && (
        <p className="muted small">
          Reason recorded by the agent: <code>{record.pending_gate.reason}</code>
        </p>
      )}
    </div>
  );
}
