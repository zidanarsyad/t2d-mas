import { useEffect, useMemo, useState } from "react";
import { ArrowDownRight, BarChart3, FlaskConical, History, Network, RotateCcw, Timer } from "lucide-react";
import { Heading, Panel, SectionTitle } from "../components/Primitives";

const format = (value, digits = 2) => Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
const arms = ["A0", "A1", "A2", "A3"];
const processes = [
  {
    id: "A0",
    name: "Rules and manual work",
    description: "A reference point: simple rules help sort issues, and people handle the rest.",
    note: "One process; no messages between agents.",
    steps: ["Ticket arrives", "Rules check it", "People route and investigate", "People review key decisions"],
  },
  {
    id: "A1",
    name: "One assistant",
    description: "One AI assistant takes on the full set of software delivery tasks.",
    note: "Tests whether one assistant is enough for the whole journey.",
    steps: ["Ticket arrives", "One assistant handles each task", "One recommendation is prepared", "People review key decisions"],
  },
  {
    id: "A2",
    name: "Specialist assistants",
    description: "Separate assistants focus on tasks such as triage, investigation, and quality checks.",
    note: "The specialists stay on the central system and pass messages.",
    steps: ["Ticket arrives", "Specialists split the work", "Central system connects results", "People review key decisions"],
  },
  {
    id: "A3",
    name: "Specialists that visit the data",
    description: "Like A2, with a Scout that can run its investigation beside local log data.",
    note: "Only approved summary fields return; the raw log data stays at its source.",
    steps: ["Ticket arrives", "Specialists split the work", "Scout visits local data", "Summary returns for review"],
  },
];

function ProcessVisualizations() {
  return <section className="experiment-process-section" aria-label="How the four approaches work">
    <SectionTitle title="How the four approaches work" detail="A0–A3 are four benchmark designs, not four agent roles."/>
    <p className="experiment-process-intro">Each follows the same ticket-to-release idea. The difference is how work is organized and where investigation happens. These diagrams explain the designs; they are not live traces of a ticket run.</p>
    <div className="experiment-process-grid">
      {processes.map((process) => <Panel className={`experiment-process-card process-${process.id.toLowerCase()}`} key={process.id}>
        <div className="experiment-process-heading"><span className={`experiment-arm arm-${process.id.toLowerCase()}`}>{process.id}</span><div><h3>{process.name}</h3><p>{process.description}</p></div></div>
        <ol className="experiment-process-flow" aria-label={`${process.id} process`}>
          {process.steps.map((step, index) => <li key={step}><span>{String(index + 1).padStart(2, "0")}</span><b>{step}</b></li>)}
        </ol>
        <small className="experiment-process-note">{process.note}</small>
      </Panel>)}
    </div>
    <div className="experiment-governance-note"><b>Human approval stays in the design.</b><span>The prototype pauses for impact assessment, change review, and release approval. Repository merges and production releases are not connected.</span></div>
  </section>;
}

export default function ExperimentsPage({ onNavigate }) {
  const [runs, setRuns] = useState([]);
  const [runId, setRunId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch("/api/experiments").then(response => {
      if (!response.ok) throw new Error("Could not load experiment results.");
      return response.json();
    }).then(data => {
      if (!active) return;
      setRuns(data.runs || []);
      if (data.runs?.length) setRunId(data.runs[0].run_id);
    }).catch(() => active && setError("Could not reach saved results. Start the project demo service, then try again."))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const selected = useMemo(() => runs.find(run => run.run_id === runId), [runs, runId]);
  const summaries = useMemo(() => {
    const rows = selected?.arms || [];
    return arms.map(arm => rows.find(row => row.arm === arm)).filter(Boolean);
  }, [selected]);
  const totalTickets = selected?.arms?.[0]?.ticket_count ? Number(selected.arms[0].ticket_count) : 0;

  return <div className="page-wrap">
    <Heading eyebrow="Compare four system designs" title="How do the approaches compare?" subtitle="See how A0–A3 organize the work, then compare their results on the same sample tickets." action={<button className="button secondary" onClick={() => onNavigate("history")}><History size={15}/>View ticket history</button>}/>
    <Panel className="experiment-note"><FlaskConical size={16}/><span><b>Classroom simulation</b><small>The tickets are computer-generated examples. Time reflects the run machine; deployment outcomes are simulated. These figures describe this experiment, not expected production performance.</small></span></Panel>

    <ProcessVisualizations/>
    <div className="experiment-score-guide"><b>How to read the scores</b><span>Severity match and early-test scores range from 0 to 1; higher is better. Similar issues is the share of tickets with a known duplicate where its matching issue appeared in the first five suggestions. Lead time and rollback are simulated; time and data transfer come from this run.</span></div>

    {error && <Panel className="experiment-empty"><b>Saved results are unavailable</b><span>{error}</span></Panel>}
    {!error && loading && <Panel className="experiment-empty" role="status">Loading saved results…</Panel>}
    {!error && !loading && !runs.length && <Panel className="experiment-empty"><b>No saved comparison runs yet</b><span>Run the project's evaluation once to create results for this screen.</span></Panel>}
    {selected && <>
      <div className="experiment-toolbar"><label>Saved comparison<select value={runId} onChange={event => setRunId(event.target.value)}>{runs.map(run => <option key={run.run_id} value={run.run_id}>{run.run_id} · {run.dataset_version}</option>)}</select></label><span>Sample set <b>{selected.dataset_version}</b></span></div>
      <div className="experiment-meta">{totalTickets} tickets per approach<span>·</span>Same tickets used for all four approaches</div>
      <div className="experiment-grid">{summaries.map(row => <Panel className={`experiment-card process-${row.arm.toLowerCase()}`} key={row.arm}>
        <div className="experiment-card-title"><span className={`experiment-arm arm-${row.arm.toLowerCase()}`}>{row.arm}</span><div><b>{row.arm_description}</b><small>{row.ticket_count} ticket evaluations</small></div></div>
        <div className="experiment-metrics">
          <span title="Macro-F1: a score for how well severity labels match the sample labels."><small>Severity match</small><b>{format(row.macro_f1_severity)}</b></span>
          <span title="Recall at five: how often a matching issue appears among the first five suggestions."><small>Similar issues found</small><b>{format(Number(row.mean_recall_at_5) * 100, 1)}%</b></span>
          <span title="NAPFD: how early the test order finds failures; higher is better."><small>Test failures found early</small><b>{format(row.napfd_mean)}</b></span>
          <span title="Simulated estimate; no real deployment service is connected."><small>Simulated lead time</small><b>{format(row.lead_time_hours_mean)} h</b></span>
          <span title="Simulated rollback rate."><small>Simulated rollback</small><b>{format(Number(row.change_failure_rate) * 100, 1)}%</b></span>
          <span title="Bytes recorded by this run on its sample workload."><small>Data sent per ticket</small><b>{Number(row.network_bytes_mean).toLocaleString()} bytes</b></span>
        </div>
      </Panel>)}</div>
      <Panel className="experiment-table-panel"><SectionTitle title="Compare the recorded results" detail="Higher severity and early-test scores are better. Time and data transfer use the selected run's measurements."/><div className="experiment-table-wrap"><table className="experiment-table"><thead><tr><th>Approach</th><th>Tickets</th><th><Timer size={12}/>Time per ticket</th><th><BarChart3 size={12}/>Severity match</th><th><ArrowDownRight size={12}/>Failures found early</th><th><Network size={12}/>Data sent / ticket</th><th><RotateCcw size={12}/>Rollback</th></tr></thead><tbody>{summaries.map(row=><tr key={row.arm}><td><span className={`experiment-arm arm-${row.arm.toLowerCase()}`}>{row.arm}</span> {row.arm_description}</td><td>{row.ticket_count}</td><td>{format(Number(row.wall_time_mean_s) * 1000, 3)} ms</td><td>{format(row.macro_f1_severity)}</td><td>{format(row.napfd_mean)}</td><td>{Number(row.network_bytes_mean).toLocaleString()} bytes</td><td>{format(Number(row.rollback_rate) * 100, 1)}%</td></tr>)}</tbody></table></div></Panel>
      <p className="experiment-footnote">{selected.measurement_note}</p>
    </>}
  </div>;
}
