import {
  ArrowRight,
  CheckCircle2,
  MessageSquareText,
  Plus,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import {
  Heading,
  Panel,
  SectionTitle,
  Severity,
} from "../components/Primitives";
import { statusLabel, workflow } from "../workflow";
export default function PipelinePage({
  records,
  onNavigate,
  loading,
  error,
  onRefresh,
}) {
  const waiting = records.filter(
      (item) => item.status === "waiting_for_review",
    ),
    active = records.filter(
      (item) => !["completed", "rejected"].includes(item.status),
    );
  return (
    <div className="page-wrap">
      <Heading
        eyebrow="From issue to improvement"
        title="Where is the work now?"
        subtitle="Follow each ticket through nine specialist stages. Human decisions are visible at every review gate."
        action={
          <button
            className="button primary"
            onClick={() => onNavigate("test", "")}
          >
            <Plus size={17} />
            Start a ticket
          </button>
        }
      />
      <div className="journey-metrics">
        {[
          [
            "Tickets in progress",
            active.length,
            "Currently moving through the prototype",
          ],
          ["Human reviews", waiting.length, "Paused until a reviewer decides"],
          [
            "Completed runs",
            records.filter((item) => item.status === "completed").length,
            "All nine prototype stages visited",
          ],
        ].map(([label, value, note]) => (
          <Panel key={label}>
            <small>{label}</small>
            <b>{loading || error ? "—" : value}</b>
            <span>{note}</span>
          </Panel>
        ))}
      </div>
      <div className="workspace-banner">
        <ShieldCheck size={21} />
        <div>
          <b>
            {waiting.length
              ? `${waiting.length} ${waiting.length === 1 ? "ticket needs" : "tickets need"} your decision`
              : "Human review is part of the workflow"}
          </b>
          <p>
            High-risk assessments, change reviews, and release proposals pause
            for a person.
          </p>
        </div>
        <button
          className="button secondary"
          onClick={() => onNavigate("approvals")}
        >
          Review inbox
          <ArrowRight size={16} />
        </button>
      </div>
      <SectionTitle
        title="The ticket journey"
        detail="Each agent shares a result with the next participant. Select a ticket to continue its run."
      />
      <div className="journey-board">
        {workflow.map((stage, index) => {
          const items = records.filter(
            (item) => item.current_stage === stage.id,
          );
          return (
            <Panel className="journey-column" key={stage.id}>
              <header>
                <span className="journey-number">{index + 1}</span>
                <h3>{stage.label}</h3>
                <small>{items.length}</small>
              </header>
              <p>{stage.description}</p>
              <div className="journey-owner">{stage.agent}</div>
              <div className="journey-tickets">
                {items.map((item) => (
                  <button
                    key={item.ticket_id}
                    className={`journey-ticket ${item.status === "waiting_for_review" ? "needs-review" : ""}`}
                    onClick={() => onNavigate("test", item.ticket_id)}
                  >
                    <span>
                      <small>{item.ticket_id}</small>
                      <Severity value={item.severity} />
                    </span>
                    <b>{item.title}</b>
                    <em>
                      {item.status === "waiting_for_review" ? (
                        <ShieldCheck size={14} />
                      ) : item.status === "completed" ? (
                        <CheckCircle2 size={14} />
                      ) : (
                        <ArrowRight size={14} />
                      )}{" "}
                      {statusLabel(item.status)}
                    </em>
                  </button>
                ))}
                {!items.length && (
                  <span className="journey-empty">No tickets here</span>
                )}
              </div>
            </Panel>
          );
        })}
      </div>
      {loading && <p role="status">Loading current ticket runs…</p>}
      {error && (
        <div className="workspace-banner error" role="alert">
          <div>
            <b>Ticket runs are unavailable</b>
            <p>{error}</p>
          </div>
          <button className="button secondary" onClick={onRefresh}>
            <RefreshCw size={16} />
            Try again
          </button>
        </div>
      )}
      {!loading && !error && !records.length && (
        <Panel className="welcome-panel">
          <MessageSquareText size={28} />
          <div>
            <h2>See a ticket move through the agents</h2>
            <p>
              Start with the sample checkout incident or describe your own
              issue. Watch the conversation and review the agents’ proposals.
            </p>
          </div>
          <button
            className="button primary"
            onClick={() => onNavigate("test", "")}
          >
            Run your first ticket
            <ArrowRight size={16} />
          </button>
        </Panel>
      )}
    </div>
  );
}
