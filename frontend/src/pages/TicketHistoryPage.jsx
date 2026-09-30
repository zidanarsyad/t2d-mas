import { useEffect, useMemo, useState } from "react";
import { Activity, Check, Clock3, FileClock, GitBranch, History, MessageSquareWarning, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { Heading, Panel, SectionTitle, Severity } from "../components/Primitives";

const armOrder = ["A0", "A1", "A2", "A3"];
const severityOptions = ["Low", "Medium", "High", "Critical"];
const number = (value, digits = 2) => Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
const label = value => value?.toLowerCase() === "qa" ? "QA" : value ? value[0].toUpperCase() + value.slice(1) : "Stage";
const runLabel = value => value?.replace(/Z$/, "") || value;
const localTime = value => value ? new Date(value).toLocaleString("en-GB", { timeZone: "Asia/Jakarta", dateStyle: "medium", timeStyle: "medium" }) + " WIB" : "Time unavailable";

export default function TicketHistoryPage() {
  const [view, setView] = useState("saved");
  const [saved, setSaved] = useState([]);
  const [savedLoading, setSavedLoading] = useState(true);
  const [savedError, setSavedError] = useState("");
  const [selectedSavedId, setSelectedSavedId] = useState("");
  const [runs, setRuns] = useState([]);
  const [runId, setRunId] = useState("");
  const [severity, setSeverity] = useState("all");
  const [history, setHistory] = useState(null);
  const [selectedId, setSelectedId] = useState("");
  const [selectedArm, setSelectedArm] = useState("A3");
  const [evalError, setEvalError] = useState("");
  const [evalLoading, setEvalLoading] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/ticket-history?limit=50").then(response => {
      if (!response.ok) return response.json().then(body => { throw new Error(body.detail || "Could not load saved ticket runs."); });
      return response.json();
    }).then(data => {
      if (!active) return;
      setSaved(data.items || []);
      setSelectedSavedId(current => data.items.some(item => item.ticket_id === current) ? current : data.items[0]?.ticket_id || "");
    }).catch(error => active && setSavedError(error.message || "Could not load saved ticket runs."))
      .finally(() => active && setSavedLoading(false));
    fetch("/api/experiments").then(response => {
      if (!response.ok) throw new Error("Could not load saved experiment runs.");
      return response.json();
    }).then(data => {
      if (!active) return;
      setRuns(data.runs || []);
      if (data.runs?.length) setRunId(data.runs[0].run_id);
    }).catch(() => active && setEvalError("No saved evaluation runs are available. Run make eval from the project root to create one."));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (view !== "evaluation" || !runId) return undefined;
    let active = true;
    setEvalLoading(true);
    setEvalError("");
    const params = new URLSearchParams({ run_id: runId, severity: severity === "all" ? severityOptions.join(",") : severity, limit: "50" });
    fetch(`/api/history?${params}`).then(response => {
      if (!response.ok) return response.json().then(body => { throw new Error(body.detail || "Could not load evaluation history."); });
      return response.json();
    }).then(data => {
      if (!active) return;
      setHistory(data);
      setSelectedId(current => data.items.some(item => `${item.seed}:${item.ticket_id}` === current) ? current : data.items[0] ? `${data.items[0].seed}:${data.items[0].ticket_id}` : "");
    }).catch(error => active && setEvalError(error.message || "Could not load evaluation history."))
      .finally(() => active && setEvalLoading(false));
    return () => { active = false; };
  }, [view, runId, severity]);

  const selected = useMemo(() => history?.items.find(item => `${item.seed}:${item.ticket_id}` === selectedId), [history, selectedId]);
  const armData = selected?.arms?.[selectedArm];
  const savedTicket = saved.find(item => item.ticket_id === selectedSavedId);
  const runOptions = useMemo(() => runs.map(run => ({ value: run.run_id, label: `${runLabel(run.run_id)} · ${run.dataset_version}` })), [runs]);

  return <div className="page-wrap history-page">
    <Heading eyebrow="Run records · agent observability" title="Ticket history" subtitle="Review saved sandbox activity and timestamped outputs, or inspect the capped synthetic evaluation sample." action={<span className="history-count"><History size={15}/>{view === "saved" ? saved.length : history?.total ?? "—"} / 50</span>}/>
    <div className="history-view-tabs" role="tablist" aria-label="Ticket history source">
      <button role="tab" aria-selected={view === "saved"} className={view === "saved" ? "active" : ""} onClick={() => setView("saved")}><FileClock size={14}/>Saved ticket runs<span>{saved.length}</span></button>
      <button role="tab" aria-selected={view === "evaluation"} className={view === "evaluation" ? "active" : ""} onClick={() => setView("evaluation")}><Activity size={14}/>Evaluation sample<span>50 max</span></button>
    </div>

    {view === "saved" && <>
      <Panel className="history-source"><ShieldCheck size={16}/><span><b>Persistent ticket audit</b><small>Sandbox and API pipeline tickets with audit events are stored in Postgres. Text is masked before storage; every stage output and ACL handoff carries a UTC timestamp and displays in WIB. The trace labels heuristic, draft-only, and simulated work explicitly.</small></span></Panel>
      {savedError && <Panel className="history-empty"><History size={22}/><b>Saved runs unavailable</b><span>{savedError}</span></Panel>}
      {!savedError && savedLoading && <Panel className="history-empty" role="status">Loading saved ticket runs…</Panel>}
      {!savedError && !savedLoading && !saved.length && <Panel className="history-empty"><History size={22}/><b>No saved sandbox runs yet</b><span>Start a ticket from Ticket Test. New runs and audit events will appear here, up to the latest 50.</span></Panel>}
      {!savedError && !savedLoading && saved.length > 0 && <div className="history-grid">
        <Panel className="history-list"><SectionTitle title="Saved runs" detail={`${saved.length} most recent sandbox tickets`}/>
          <div className="history-table-head saved-history-head"><span>Ticket</span><span>Severity</span><span>Started</span></div>
          <div className="history-rows">{saved.map(item => <button key={item.ticket_id} className={`history-row saved-history-row ${selectedSavedId === item.ticket_id ? "active" : ""}`} onClick={() => setSelectedSavedId(item.ticket_id)}><span className="history-ticket-label"><b>{item.ticket_id}</b><small>{item.title}</small></span><Severity value={item.severity}/><span>{localTime(item.process_started_at)}</span></button>)}</div>
        </Panel>
        <Panel className="history-detail saved-run-detail">{savedTicket ? <>
          <div className="history-detail-heading"><div><small className="eyebrow">Persistent process record</small><h2>{savedTicket.ticket_id}</h2></div><Severity value={savedTicket.severity}/></div>
          <article className="original-ticket"><div className="original-ticket-label"><MessageSquareWarning size={15}/><b>Original ticket</b><span>{savedTicket.events.length} process events</span></div><h3>{savedTicket.title}</h3><p>{savedTicket.body}</p><small>Process started {localTime(savedTicket.process_started_at)}</small></article>
          <div className="history-stage-title"><SectionTitle title="Agent and process trace" detail="Each event is shown with its recorded time and audit status"/></div>
          <ol className="saved-event-list">{savedTicket.events.map((event, index) => {
            const outputEvent = event.action === "agent_output";
            const scaffoldEvent = event.action === "stage_scaffold";
            const reviewEvent = ["human_approval", "review_revision_requested", "human_review_feedback"].includes(event.action);
            return <li key={`${event.occurred_at}-${event.action}-${index}`} className={reviewEvent ? `review-event ${event.decision}` : scaffoldEvent ? "scaffold-event" : ""}>
              <span className="saved-event-icon">{reviewEvent ? event.decision === "approved" ? <Check size={13}/> : <X size={13}/> : outputEvent ? <Activity size={13}/> : <GitBranch size={13}/>}</span>
              <div className="saved-event-content"><div className="saved-event-top"><b>{event.agent || "Orchestrator"} · {label(event.stage || event.action.replaceAll("_", " "))}</b><time>{localTime(event.occurred_at)}</time></div>
                <small className="saved-event-state">{scaffoldEvent ? "Scaffold only · specialist not invoked" : reviewEvent ? `${event.decision} · ${event.approver || "reviewer"}` : outputEvent ? `${event.decision} · ${event.execution_mode?.replaceAll("_", " ") || "recorded output"}` : event.decision?.replaceAll("_", " ") || event.action.replaceAll("_", " ")}</small>
                {event.performative && <div className="saved-message-route"><b>{event.performative}</b><span>{event.agent}</span><span>→</span><span>{Array.isArray(event.receivers) ? event.receivers.join(", ") : event.receivers || "No recipient"}</span>{event.message_id && <small>{event.message_id}</small>}</div>}
                {event.output && <pre>{JSON.stringify(event.output, null, 2)}</pre>}
                {event.note && <blockquote><b>Reviewer note · {event.intent?.replaceAll("_", " ") || "decision"}</b><br/>{event.note}{event.interpretation && <><small>Agent interpretation{event.interpretation.interpreter ? ` · ${event.interpretation.interpreter}` : ""}</small><pre>{JSON.stringify(event.interpretation, null, 2)}</pre></>}{event.revision && <small>Revision {event.revision} · feedback recorded with this ticket</small>}</blockquote>}
              </div>
            </li>;
          })}</ol>
        </> : <div className="history-empty"><History size={22}/><b>Select a saved run</b><span>Choose a ticket to inspect its input and timestamped agent activity.</span></div>}</Panel>
      </div>}
    </>}

    {view === "evaluation" && <>
      <Panel className="history-source"><ShieldAlert size={16}/><span><b>Synthetic evaluation history</b><small>Examples are generated and outcomes are simulated. This list is capped at 50 ticket records. A 50-row sample approximates the requested 53% Low, 31% Medium, 11% High, 5% Severe mix with integer counts: 26 Low, 16 Medium, 6 High, and 2 Severe (Critical), or 52%, 32%, 12%, 4%.</small></span></Panel>
      <div className="history-toolbar"><label>Evaluation run<select value={runId} onChange={event => setRunId(event.target.value)} disabled={!runOptions.length}>{runOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><label>Severity<select value={severity} onChange={event => setSeverity(event.target.value)}><option value="all">All severities</option>{severityOptions.map(item => <option key={item} value={item}>{item === "Critical" ? "Severe (Critical)" : item}</option>)}</select></label></div>
      {evalError && <Panel className="history-empty"><History size={22}/><b>Evaluation history unavailable</b><span>{evalError}</span></Panel>}
      {!evalError && evalLoading && <Panel className="history-empty" role="status">Loading evaluation history…</Panel>}
      {!evalError && !evalLoading && history && <>
        <div className="history-meta">Run <b>{runLabel(history.run_id)}</b><span>·</span>Dataset <b>{history.dataset_version}</b><span>·</span>Showing {history.total} of {history.matching_total} matching records</div>
        <div className="history-severity-mix">Severity mix: {Object.entries(history.severity_counts || {}).filter(([, count]) => count).map(([name, count]) => `${name === "Critical" ? "Severe" : name} ${count}`).join(" · ") || "No matching tickets"}</div>
        <div className="history-grid">
          <Panel className="history-list"><SectionTitle title="Evaluation tickets" detail={`${history.total} sample records · select one to inspect outcomes`}/>
            <div className="history-table-head"><span>Ticket</span><span>Seed</span><span>Severity</span><span>Duplicate</span><span>Arms</span></div>
            <div className="history-rows">{history.items.map(item => <button key={`${item.seed}:${item.ticket_id}`} className={`history-row ${selectedId === `${item.seed}:${item.ticket_id}` ? "active" : ""}`} onClick={() => setSelectedId(`${item.seed}:${item.ticket_id}`)}><span className="history-ticket-label"><b>{item.ticket_id}</b><small>{item.title}</small></span><span>{item.seed}</span><Severity value={item.severity}/><span>{item.duplicate_of || "—"}</span><span>{Object.keys(item.arms).length}/4</span></button>)}{!history.items.length && <div className="history-empty-inline">No tickets match this severity.</div>}</div>
          </Panel>
          <Panel className="history-detail">{selected && armData ? <>
            <div className="history-detail-heading"><div><small className="eyebrow">Seed {selected.seed} · evaluation record</small><h2>{selected.ticket_id}</h2></div><Severity value={selected.severity}/></div>
            <article className="original-ticket"><div className="original-ticket-label"><MessageSquareWarning size={15}/><b>Original ticket</b><span>{selected.component || "Synthetic dataset"}</span></div><h3>{selected.title || selected.ticket_id}</h3><p>{selected.body || "Original description is not available for this saved run."}</p><small>Created {selected.created_at ? localTime(selected.created_at) : "in the synthetic dataset"}{selected.duplicate_of ? ` · Follow-up of ${selected.duplicate_of}` : ""}</small></article>
            <label className="arm-select-label">Experiment arm<select value={selectedArm} onChange={event => setSelectedArm(event.target.value)}>{armOrder.filter(arm => selected.arms[arm]).map(arm => <option key={arm} value={arm}>{arm} · {selected.arms[arm].arm_description}</option>)}</select></label>
            <p className="arm-description">{armData.arm_description}</p>
            {armData.review_decision !== "not_required" && <div className={`history-review-note ${armData.review_decision}`}><div><ShieldCheck size={14}/><b>Synthetic severity review · {label(armData.review_decision)}</b></div><p>{armData.review_note}</p></div>}
            <div className="history-outcomes"><div><small>Predicted severity</small><b>{armData.severity_predicted} · {number(armData.severity_confidence * 100, 1)}% confidence</b></div><div><small>Deployment</small><b className={armData.deployment_success ? "history-success" : "history-failure"}>{armData.deployment_success ? <><Check size={13}/> Success</> : <><X size={13}/> Failed</>}</b></div><div><small>Simulated lead time</small><b>{number(armData.lead_time_hours)} h</b></div><div><small>Network / messages</small><b>{Number(armData.network_bytes).toLocaleString()} B · {armData.messages}</b></div></div>
            <div className="history-stage-title"><SectionTitle title="Processing stages" detail="Synthetic measurements; no agent output is generated for these eval rows"/></div>
            <ol className="processing-stages">{armData.stages.map((stage, index) => <li key={stage.stage}><span className="stage-step">{index + 1}</span><div><b>{label(stage.stage)}</b><small>{number(stage.wall_time_seconds * 1000, 3)} ms</small></div><span className="stage-metrics"><span><GitBranch size={11}/>{stage.network_bytes} B</span><span><Activity size={11}/>{stage.messages} msgs</span><span><Clock3 size={11}/>{stage.llm_tokens_estimated} est. tokens</span></span></li>)}</ol>
          </> : <div className="history-empty"><History size={22}/><b>Select a ticket</b><span>Choose a ticket to review its original report and processing history.</span></div>}</Panel>
        </div>
      </>}
    </>}
  </div>;
}
