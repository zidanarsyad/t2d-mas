import { useEffect, useMemo, useState } from "react";
import { ArrowDownRight, BarChart3, FlaskConical, History, Network, RotateCcw, Timer } from "lucide-react";
import { Heading, Panel, SectionTitle } from "../components/Primitives";

const format = (value, digits = 2) => Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
const arms = ["A0", "A1", "A2", "A3"];

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
    }).catch(() => active && setError("Could not reach saved evaluation results. Rebuild and start Docker Compose, then try again."))
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
    <Heading eyebrow="Reproducible evaluation · four system designs" title="Experiments" subtitle="Compare the saved A0–A3 evaluation runs, then open the ticket history to inspect Low and Medium tickets stage by stage." action={<button className="button secondary" onClick={() => onNavigate("history")}><History size={15}/>Open ticket history</button>}/>
    <Panel className="experiment-note"><FlaskConical size={16}/><span><b>Seeded synthetic experiment</b><small>Five fixed seeds compare four approaches on identical ticket sets. Timings reflect the recorded run host; deployments and outcomes are simulated.</small></span></Panel>
    {error && <Panel className="experiment-empty"><b>Experiment results unavailable</b><span>{error}</span></Panel>}
    {!error && loading && <Panel className="experiment-empty" role="status">Loading saved experiments…</Panel>}
    {!error && !loading && !runs.length && <Panel className="experiment-empty"><b>No saved experiment runs</b><span>From the project root, install `eval/requirements.txt` and run `make eval` to generate the first results.</span></Panel>}
    {selected && <>
      <div className="experiment-toolbar"><label>Saved run<select value={runId} onChange={event => setRunId(event.target.value)}>{runs.map(run => <option key={run.run_id} value={run.run_id}>{run.run_id} · {run.dataset_version}</option>)}</select></label><span>Dataset <b>{selected.dataset_version}</b></span></div>
      <div className="experiment-meta">Run <b>{selected.run_id}</b><span>·</span>{selected.seeds.length} seeds <b>{selected.seeds.join(", ")}</b><span>·</span>{totalTickets} tickets per arm</div>
      <div className="experiment-grid">{summaries.map(row => <Panel className="experiment-card" key={row.arm}><div className="experiment-card-title"><span className={`experiment-arm arm-${row.arm.toLowerCase()}`}>{row.arm}</span><div><b>{row.arm_description}</b><small>{row.ticket_count} ticket evaluations</small></div></div><div className="experiment-metrics"><span><small>Severity F1</small><b>{format(row.macro_f1_severity)}</b></span><span><small>Recall@5</small><b>{format(row.mean_recall_at_5)}</b></span><span><small>NAPFD</small><b>{format(row.napfd_mean)}</b></span><span><small>Lead time</small><b>{format(row.lead_time_hours_mean)} h</b></span><span><small>Failure rate</small><b>{format(Number(row.change_failure_rate) * 100, 1)}%</b></span><span><small>Network / ticket</small><b>{Number(row.network_bytes_mean).toLocaleString()} B</b></span></div></Panel>)}</div>
      <Panel className="experiment-table-panel"><SectionTitle title="Run comparison" detail="Per-arm summary from the selected result bundle"/><div className="experiment-table-wrap"><table className="experiment-table"><thead><tr><th>Arm</th><th>Approach</th><th>Tickets</th><th><Timer size={12}/>Mean time</th><th><BarChart3 size={12}/>Severity F1</th><th><ArrowDownRight size={12}/>NAPFD</th><th><Network size={12}/>Network</th><th><RotateCcw size={12}/>Rollback</th></tr></thead><tbody>{summaries.map(row=><tr key={row.arm}><td><span className={`experiment-arm arm-${row.arm.toLowerCase()}`}>{row.arm}</span></td><td>{row.arm_description}</td><td>{row.ticket_count}</td><td>{format(Number(row.wall_time_mean_s) * 1000, 3)} ms</td><td>{format(row.macro_f1_severity)}</td><td>{format(row.napfd_mean)}</td><td>{Number(row.network_bytes_mean).toLocaleString()} B</td><td>{format(Number(row.rollback_rate) * 100, 1)}%</td></tr>)}</tbody></table></div></Panel>
      <p className="experiment-footnote">{selected.measurement_note}</p>
    </>}
  </div>;
}
