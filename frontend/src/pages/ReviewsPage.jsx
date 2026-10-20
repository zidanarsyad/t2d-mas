import { useState } from "react";
import { ArrowRight, CircleCheck, Lock, RefreshCw, ShieldCheck, Undo2 } from "lucide-react";
import GateEvidence from "../components/GateEvidence";
import ReviewControls from "../components/ReviewControls";
import StageDetails from "../components/StageDetails";
import Term from "../components/Term";
import { EmptyState, Heading, Notice, Panel, SectionTitle, Severity } from "../components/Primitives";
import { formatDuration } from "../lib/format.js";
import { gateLabel, gateRule, policySourceLabel, reviewPriority } from "../lib/policy.js";
import { clarificationQuestion, gates, isWaiting, stageInfo } from "../lib/workflow.js";
import { useNow } from "../hooks/useNow";

const SEVERITIES = ["All", "Critical", "High", "Medium", "Low"];

/** What the last decision did to the ticket, in one sentence. */
function savedOutcome(record, policy) {
  if (clarificationQuestion(record)) return "The agent could not act on that note; its question is shown in the review form.";
  if (record.status === "rejected") return "The run is stopped; your reason stays in its audit log.";
  if (record.status === "duplicate") return `Linked as a duplicate of ${record.duplicate_of}; this run is closed.`;
  if (record.status === "completed") return "The run is finished.";
  if (record.status === "waiting_for_review") return `It now waits at the next gate: ${gateLabel(record.pending_gate?.gate, policy)}.`;
  return "The ticket can continue. Open it to run the next steps.";
}

export default function ReviewsPage({ workspace, onNavigate }) {
  const { records, policy, mode, upsert, loading, error, refresh } = workspace;
  const now = useNow(30000);
  const [severity, setSeverity] = useState("All");
  const [selectedId, setSelectedId] = useState("");
  const [saved, setSaved] = useState(null);
  const pending = records.filter(isWaiting);
  const ordered = pending
    .filter((item) => severity === "All" || item.severity === severity)
    .map((record) => ({ record, priority: reviewPriority(record, policy, now) }))
    .sort((a, b) => b.priority.score - a.priority.score);
  const selected = ordered.find((item) => item.record.ticket_id === selectedId)?.record || ordered[0]?.record || null;

  return (
    <div className="page">
      <Heading
        eyebrow="Human reviews"
        title="What needs my decision?"
        what="Every ticket that waits at a human gate, riskiest and longest-waiting first, with the evidence and the policy limits."
        why="Agents only act alone inside the policy; everything else needs your approval, and your reason is audited."
      />
      {mode !== "live" && (
        <Notice tone="warn" title="Replay mode">
          Reviews need the backend, because a decision changes a real run. The gate table below still shows the rules.
        </Notice>
      )}
      {mode === "live" && error && (
        <Notice tone="bad" title="The review queue could not be loaded" action={<button type="button" className="button" onClick={refresh}><RefreshCw size={15} aria-hidden="true" /> Try again</button>}>
          {error}
        </Notice>
      )}
      {saved && (
        <Notice tone="ok" icon={CircleCheck} title={`Decision saved for ${saved.ticket_id}`} action={<button type="button" className="button" onClick={() => onNavigate("run", saved.ticket_id)}>Open the ticket <ArrowRight size={15} aria-hidden="true" /></button>}>
          {savedOutcome(saved, policy)}
        </Notice>
      )}

      {mode === "live" && (
        <div className="split split-reviews">
          <Panel className="list-panel">
            <SectionTitle
              title={`Waiting for a human (${pending.length})`}
              detail="Sorted by severity risk × minutes waiting."
              level={3}
              action={
                <select aria-label="Filter by severity" value={severity} onChange={(event) => setSeverity(event.target.value)}>
                  {SEVERITIES.map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              }
            />
            {loading && (
              <p className="muted" role="status">
                Loading…
              </p>
            )}
            <ul className="plain-list review-queue">
              {ordered.map(({ record, priority }) => (
                <li key={record.ticket_id}>
                  <button type="button" className={`list-button ${record.ticket_id === selected?.ticket_id ? "is-selected" : ""}`} aria-pressed={record.ticket_id === selected?.ticket_id} onClick={() => setSelectedId(record.ticket_id)}>
                    <span>
                      <b>{gateLabel(record.pending_gate?.gate, policy)}</b>
                      <small>
                        {record.ticket_id} · {record.title}
                      </small>
                      <small>Waiting {formatDuration(priority.waitingMinutes * 60)}</small>
                    </span>
                    <Severity value={record.severity} />
                  </button>
                </li>
              ))}
            </ul>
            {!ordered.length && !loading && (
              <EmptyState icon={ShieldCheck} title={pending.length ? "No match for this filter" : "Nothing waits for you"}>
                {pending.length ? "Choose another severity." : "Run a ticket; its gates appear here."}
              </EmptyState>
            )}
          </Panel>
          {selected ? (
            <Panel className="detail-panel">
              <p className="eyebrow">
                {selected.ticket_id} · {stageInfo(selected.pending_gate?.stage).name}
              </p>
              <h2>{selected.pending_gate?.question || gateLabel(selected.pending_gate?.gate, policy)}</h2>
              <p>{selected.title}</p>
              <SectionTitle title="Why the agent paused" level={3} />
              <GateEvidence record={selected} policy={policy} />
              <SectionTitle title="What the agent proposes" level={3} />
              <StageDetails record={selected} stageId={selected.pending_gate?.stage || selected.current_stage} policy={policy} />
              <SectionTitle title="Your decision" level={3} />
              <ReviewControls
                key={`${selected.ticket_id}:${selected.pending_gate?.gate}:${selected.reviews.length}`}
                record={selected}
                onRecord={(next) => {
                  const record = upsert(next);
                  setSaved(record);
                  return record;
                }}
              />
            </Panel>
          ) : (
            <Panel className="detail-panel">
              <EmptyState icon={ShieldCheck} title="A human gate is a deliberate pause">
                Select a ticket to see its evidence and decide.
              </EmptyState>
            </Panel>
          )}
        </div>
      )}

      <Panel>
        <SectionTitle title="The six human gates" detail={policySourceLabel(policy)} />
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Gate</th>
                <th scope="col">Stage · agent</th>
                <th scope="col">The agent continues alone when</th>
                <th scope="col">A person decides when</th>
                <th scope="col">Undo?</th>
              </tr>
            </thead>
            <tbody>
              {gates.map((gate) => {
                const rule = gateRule(gate.id, policy);
                return (
                  <tr key={gate.id}>
                    <th scope="row">
                      {gateLabel(gate.id, policy)}
                      <code className="raw-name">{gate.id}</code>
                    </th>
                    <td>
                      {stageInfo(gate.stage).name} · {gate.agent}
                    </td>
                    <td>{rule.autonomous}</td>
                    <td>{rule.human}</td>
                    <td>
                      {gate.irreversible ? (
                        <span className="text-bad">
                          <Lock size={14} aria-hidden="true" /> Irreversible
                        </span>
                      ) : (
                        <span className="text-ok">
                          <Undo2 size={14} aria-hidden="true" /> Reversible
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="muted small">
          The <Term id="autonomy-gate">autonomy gate</Term> uses <Term id="tau">τ</Term> and <Term id="risk-max">R_max</Term>; duplicates use the{" "}
          <Term id="duplicate-bands">similarity bands</Term>; the canary uses the <Term id="risk-score">release risk score</Term>.
        </p>
      </Panel>
    </div>
  );
}
