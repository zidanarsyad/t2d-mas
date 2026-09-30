import { useState } from "react";
import { ArrowRight, RefreshCw, ShieldCheck } from "lucide-react";
import {
  Heading,
  Panel,
  SectionTitle,
  Severity,
} from "../components/Primitives";
import OutputSummary from "../components/OutputSummary";
import ReviewControls from "../components/ReviewControls";
import { checkpointLabel, stageInfo } from "../workflow";
const risk = { Low: 0.1, Medium: 0.3, High: 0.6, Critical: 1 };
export default function ApprovalsPage({
  records,
  onRecord,
  onNavigate,
  loading,
  error,
  onRefresh,
}) {
  const [selectedId, setSelectedId] = useState(""),
    [severity, setSeverity] = useState("All"),
    [lastReviewed, setLastReviewed] = useState(null);
  const pending = records.filter(
    (item) => item.status === "waiting_for_review",
  );
  const ordered = pending
    .filter((item) => severity === "All" || item.severity === severity)
    .sort(
      (a, b) =>
        (risk[b.severity] || 0) *
          (Date.now() - Date.parse(b.review_requested_at || b.created_at) ||
            1) -
        (risk[a.severity] || 0) *
          (Date.now() - Date.parse(a.review_requested_at || a.created_at) || 1),
    );
  const selected =
    ordered.find((item) => item.ticket_id === selectedId) || ordered[0];
  return (
    <div className="page-wrap">
      <Heading
        eyebrow="People stay in control"
        title="What needs your decision?"
        subtitle="Inspect the agent’s proposal, explain your decision, and keep the ticket moving safely."
        action={
          <span className="approval-count">
            <ShieldCheck size={17} />
            {pending.length} pending reviews
          </span>
        }
      />
      {lastReviewed && (
        <div className="workspace-banner" role="status">
          <ShieldCheck size={20} />
          <div>
            <b>Decision recorded for {lastReviewed.ticket_id}</b>
            <p>
              {lastReviewed.reviews.at(-1)?.decision === "changes_requested"
                ? "The agent revised its proposal. Open the ticket to inspect the changes and continue."
                : lastReviewed.status === "rejected"
                  ? "The run is stopped. Your reason remains in its audit history."
                  : "Your note is saved with this ticket."}
            </p>
          </div>
          <button
            className="button secondary"
            onClick={() => onNavigate("test", lastReviewed.ticket_id)}
          >
            Open ticket
            <ArrowRight size={16} />
          </button>
        </div>
      )}
      {error && (
        <div className="workspace-banner error" role="alert">
          <div>
            <b>Review queue unavailable</b>
            <p>{error}</p>
          </div>
          <button className="button secondary" onClick={onRefresh}>
            <RefreshCw size={16} />
            Try again
          </button>
        </div>
      )}
      {loading && <p role="status">Loading review requests…</p>}
      <div className="review-inbox-layout">
        <Panel className="review-inbox-list">
          <div className="focus-heading">
            <SectionTitle
              title="Waiting for a person"
              detail="Sorted by impact risk and time waiting for review."
            />
            <select
              aria-label="Filter review severity"
              value={severity}
              onChange={(event) => setSeverity(event.target.value)}
            >
              {["All", "Critical", "High", "Medium", "Low"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </div>
          {ordered.map((item) => (
            <button
              className={`review-request ${item.ticket_id === selected?.ticket_id ? "selected" : ""}`}
              key={item.ticket_id}
              onClick={() => setSelectedId(item.ticket_id)}
            >
              <Severity value={item.severity} />
              <b>{item.title}</b>
              <span>{checkpointLabel(item.waiting_for)}</span>
              <small>
                {item.ticket_id} · {stageInfo(item.current_stage).agent}
              </small>
            </button>
          ))}
          {!ordered.length && !loading && !error && (
            <div className="empty-state">
              <ShieldCheck size={28} />
              <h2>
                {pending.length
                  ? "No matching reviews"
                  : "You’re all caught up"}
              </h2>
              <p>
                {pending.length
                  ? "Choose a different severity to see pending requests."
                  : "Run a ticket to see human review checkpoints here."}
              </p>
              <button
                className="button secondary"
                onClick={() => onNavigate("test", "")}
              >
                Run a ticket
                <ArrowRight size={16} />
              </button>
            </div>
          )}
        </Panel>
        {selected ? (
          <Panel className="review-inbox-detail">
            <small className="eyebrow">
              {selected.ticket_id} · {stageInfo(selected.current_stage).agent}
            </small>
            <h2>{checkpointLabel(selected.waiting_for)}</h2>
            <p>{selected.title}</p>
            <div className="checkpoint-callout">
              <ShieldCheck size={20} />
              <div>
                <b>Why the agent paused</b>
                <p>
                  {selected.waiting_for === "autonomy_gate"
                    ? `${selected.severity} impact with assessment score ${selected.severity_confidence.toFixed(2)}. Automatic decisions require a score of at least 0.70 and risk no greater than 0.60. ${selected.severity_rationale}`
                    : selected.waiting_for === "pr_merge"
                      ? "Change review always needs a person. This prototype contains a draft request and verification checklist; no patch or CI run has been executed."
                      : "A full release requires a person’s approval. This is a rollout proposal; no production deployment will execute."}
                </p>
              </div>
            </div>
            <SectionTitle title="Agent proposal" />
            <OutputSummary
              output={selected.agent_outputs?.[selected.current_stage]}
            />
            <button
              className="text-button"
              onClick={() => onNavigate("communications", selected.ticket_id)}
            >
              Inspect the agent conversation
              <ArrowRight size={15} />
            </button>
            <ReviewControls
              key={`${selected.ticket_id}:${selected.waiting_for}`}
              record={selected}
              onRecord={(next) => {
                onRecord(next);
                setLastReviewed(next);
              }}
            />
          </Panel>
        ) : (
          <Panel className="empty-state review-placeholder">
            <ShieldCheck size={32} />
            <h2>Human approval is a deliberate checkpoint</h2>
            <p>
              Select a request to inspect its evidence and record a decision.
              Completed decisions stay in the ticket’s history.
            </p>
          </Panel>
        )}
      </div>
    </div>
  );
}
