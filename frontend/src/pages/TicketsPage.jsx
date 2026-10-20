import { useEffect, useState } from "react";
import { CirclePlay, Database, Hourglass, Kanban, RefreshCw } from "lucide-react";
import { api, isUnavailable } from "../api";
import TraceTimeline from "../components/TraceTimeline";
import { EmptyState, Heading, Notice, Panel, SectionTitle, Severity, SourceBadge, StatusBadge, Tabs, tabPanelProps } from "../components/Primitives";
import { formatDuration, formatTime, secondsSince } from "../lib/format.js";
import { gateLabel } from "../lib/policy.js";
import { entriesFromAudit } from "../lib/trace.js";
import { currentAgent, isWaiting, shortAgentName, stageEnteredAt, stages } from "../lib/workflow.js";
import { useNow } from "../hooks/useNow";

// Shown on the board in replay mode, clearly labelled as illustrative.
const REPLAY_TICKET = {
  ticket_id: "TCK-1042",
  title: "Checkout crashes when paying during the flash sale",
  severity: "Critical",
  status: "waiting_for_review",
  current_stage: "deployment",
  waiting_for: "release_signoff",
  pending_gate: { gate: "release_signoff" },
  stages: [],
  illustrative: true,
};

export default function TicketsPage({ workspace, onNavigate, sub }) {
  const [tab, setTab] = useState(sub === "saved" ? "saved" : "board");
  return (
    <div className="page">
      <Heading
        eyebrow="Tickets"
        title="Where is the work, and what is blocked?"
        what="Every ticket in the stage it is in now, with its agent, time in stage and whether it waits for a person."
        why="Blocked work is easy to miss; the board shows it at a glance."
        action={
          <button type="button" className="button button-primary" onClick={() => onNavigate("run", "")}>
            <CirclePlay size={16} aria-hidden="true" />
            Run a ticket
          </button>
        }
      />
      <Tabs
        tabs={[
          { id: "board", label: "Board", icon: Kanban, count: workspace.records.length },
          { id: "saved", label: "Saved runs", icon: Database },
        ]}
        value={tab}
        onChange={setTab}
        label="Ticket views"
        idPrefix="tickets"
      />
      <div {...tabPanelProps("tickets", tab)}>{tab === "board" ? <Board workspace={workspace} onNavigate={onNavigate} /> : <SavedRuns workspace={workspace} onNavigate={onNavigate} />}</div>
    </div>
  );
}

function Board({ workspace, onNavigate }) {
  const { records, loading, error, refresh, mode, policy } = workspace;
  const now = useNow(30000);
  const live = mode === "live";
  const open = live ? records.filter((item) => ["running", "waiting_for_review"].includes(item.status)) : [REPLAY_TICKET];
  const closed = live ? records.filter((item) => !["running", "waiting_for_review"].includes(item.status)) : [];
  const waiting = open.filter(isWaiting).length;

  return (
    <>
      {!live && (
        <Notice tone="warn" title="Replay mode">
          Live tickets need the backend. The one card below is the illustrative TCK-1042 story, waiting for its release sign-off.
        </Notice>
      )}
      {live && error && (
        <Notice tone="bad" title="Tickets could not be loaded" action={<button type="button" className="button" onClick={refresh}><RefreshCw size={15} aria-hidden="true" /> Try again</button>}>
          {error}
        </Notice>
      )}
      <div className="fact-row">
        <Panel className="fact">
          <b>{open.length}</b>
          <small>in progress</small>
        </Panel>
        <Panel className="fact">
          <b>{waiting}</b>
          <small>waiting for a human</small>
        </Panel>
        <Panel className="fact">
          <b>{closed.length}</b>
          <small>finished, stopped or linked</small>
        </Panel>
      </div>
      {loading && live && (
        <p className="muted" role="status">
          Loading tickets…
        </p>
      )}
      <div className="board" role="list" aria-label="Board columns, one per stage">
        {stages.map((stage, index) => {
          const items = open.filter((item) => item.current_stage === stage.id);
          return (
            <section key={stage.id} className="board-column" role="listitem" aria-label={`${stage.name}: ${items.length} tickets`}>
              <header>
                <span className="stage-number" aria-hidden="true">
                  {index + 1}
                </span>
                <h3>{stage.name}</h3>
                <small>{items.length}</small>
              </header>
              <p className="muted small">{stage.agent}</p>
              <div className="board-cards">
                {items.map((item) => {
                  const entered = stageEnteredAt(item, item.current_stage);
                  return (
                    <button key={item.ticket_id} type="button" className={`board-card ${isWaiting(item) ? "is-waiting" : ""}`} onClick={() => (item.illustrative ? onNavigate("overview") : onNavigate("run", item.ticket_id))}>
                      <span className="board-card-top">
                        <code>{item.ticket_id}</code>
                        <Severity value={item.severity} />
                      </span>
                      <b>{item.title}</b>
                      <small>{shortAgentName(currentAgent(item))}</small>
                      {isWaiting(item) ? (
                        <span className="waiting-badge">
                          <Hourglass size={13} aria-hidden="true" />
                          Waiting for a human: {gateLabel(item.pending_gate?.gate, policy)}
                        </span>
                      ) : (
                        <small>{entered ? `In this stage for ${formatDuration(secondsSince(entered, now))}` : "Just started"}</small>
                      )}
                      {item.illustrative && <SourceBadge source="replay" />}
                    </button>
                  );
                })}
                {!items.length && <span className="board-empty">No tickets</span>}
              </div>
            </section>
          );
        })}
      </div>
      {closed.length > 0 && (
        <Panel>
          <SectionTitle title="Finished, stopped or linked" detail="Open one to see its full journey." />
          <ul className="plain-list closed-list">
            {closed.map((item) => (
              <li key={item.ticket_id}>
                <button type="button" className="continue-ticket" onClick={() => onNavigate("run", item.ticket_id)}>
                  <span>
                    <b>{item.title}</b>
                    <small>
                      {item.ticket_id}
                      {item.duplicate_of ? ` · duplicate of ${item.duplicate_of}` : ""}
                    </small>
                  </span>
                  <StatusBadge status={item.status} />
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {live && !loading && !records.length && <EmptyState title="No tickets yet">Start one from Run a ticket and it appears here.</EmptyState>}
    </>
  );
}

function SavedRuns({ workspace, onNavigate }) {
  const { policy, records } = workspace;
  const [state, setState] = useState({ items: [], loading: true, error: "", offline: false });
  const [selectedId, setSelectedId] = useState("");

  useEffect(() => {
    let active = true;
    api
      .ticketHistory(50)
      .then((items) => {
        if (!active) return;
        setState({ items, loading: false, error: "", offline: false });
        setSelectedId((current) => (items.some((item) => item.ticket_id === current) ? current : items[0]?.ticket_id || ""));
      })
      .catch((err) => active && setState({ items: [], loading: false, error: err.message, offline: isUnavailable(err) }));
    return () => {
      active = false;
    };
  }, [workspace.mode]);

  const selected = state.items.find((item) => item.ticket_id === selectedId);
  if (state.loading)
    return (
      <p className="muted" role="status">
        Loading saved runs…
      </p>
    );
  if (state.offline) return <Notice tone="warn" title="Saved runs need the backend">They are read from the audit log (Postgres, or memory in local mode).</Notice>;
  if (state.error) return <Notice tone="bad" title="Saved runs could not be loaded">{state.error}</Notice>;
  if (!state.items.length) return <EmptyState title="No saved runs yet">Every ticket you run is saved with its audit events, up to the latest 50.</EmptyState>;

  return (
    <div className="split">
      <Panel className="list-panel">
        <SectionTitle title="Saved runs" detail={`${state.items.length} most recent tickets`} level={3} />
        <ul className="plain-list saved-list">
          {state.items.map((item) => (
            <li key={item.ticket_id}>
              <button type="button" className={`list-button ${item.ticket_id === selectedId ? "is-selected" : ""}`} aria-pressed={item.ticket_id === selectedId} onClick={() => setSelectedId(item.ticket_id)}>
                <span>
                  <b>{item.ticket_id}</b>
                  <small>{item.title}</small>
                </span>
                <Severity value={item.severity} />
              </button>
            </li>
          ))}
        </ul>
      </Panel>
      {selected && (
        <Panel className="detail-panel">
          <SectionTitle
            title={selected.ticket_id}
            detail={`Started ${formatTime(selected.process_started_at, { date: true })} · ${selected.events.length} audit events`}
            action={
              records.some((item) => item.ticket_id === selected.ticket_id) && (
                <button type="button" className="button button-small" onClick={() => onNavigate("run", selected.ticket_id)}>
                  Open the run
                </button>
              )
            }
          />
          <blockquote className="original-text">
            <b>{selected.title}</b>
            <p>{selected.body}</p>
          </blockquote>
          <TraceTimeline entries={entriesFromAudit(selected.events, policy)} />
        </Panel>
      )}
    </div>
  );
}
