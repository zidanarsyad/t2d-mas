import { useEffect, useMemo, useState } from "react";
import { BarChart3, CircleCheck, CircleX, FlaskConical, ListChecks } from "lucide-react";
import { api, isUnavailable } from "../api";
import Term from "../components/Term";
import { EmptyState, Heading, Notice, Panel, SectionTitle, Severity, Tabs, Tag, tabPanelProps } from "../components/Primitives";
import { armProcesses } from "../data/reportExamples.js";
import { barWidth, experimentMetrics, formatBytes, formatNumber, formatRunLabel, formatTime } from "../lib/format.js";

const ARMS = ["A0", "A1", "A2", "A3"];
const KIND_TAG = { measured: { tone: "green", label: "measured" }, score: { tone: "blue", label: "scored" }, simulated: { tone: "violet", label: "simulated" } };
const METRIC_TERMS = { macro_f1_severity: "macro-f1", mean_recall_at_5: "recall-at-5", napfd_mean: "napfd" };

export default function ExperimentsPage({ workspace, sub }) {
  const [tab, setTab] = useState(sub === "samples" ? "samples" : "results");
  const [runs, setRuns] = useState({ items: [], loading: true, error: "", offline: false });
  const [runId, setRunId] = useState("");

  useEffect(() => {
    let active = true;
    api
      .experiments()
      .then((items) => {
        if (!active) return;
        setRuns({ items, loading: false, error: "", offline: false });
        setRunId((current) => current || items[0]?.run_id || "");
      })
      .catch((err) => active && setRuns({ items: [], loading: false, error: err.message, offline: isUnavailable(err) }));
    return () => {
      active = false;
    };
  }, [workspace.mode]);

  const run = runs.items.find((item) => item.run_id === runId);

  return (
    <div className="page">
      <Heading
        eyebrow="Experiment results"
        title="What did A0–A3 measure?"
        what="The saved evaluation: four system designs run on the same seeded synthetic tickets, five seeds × 100 tickets."
        why="It is the evidence behind the report's comparison, with measured, scored and simulated numbers kept apart."
      />
      {runs.offline && (
        <Notice tone="warn" title="Saved results need the backend">
          They are read from the <code>results/</code> folder by the API. The four designs are explained below.
        </Notice>
      )}
      {!runs.offline && runs.error && <Notice tone="bad" title="Results could not be loaded">{runs.error}</Notice>}
      {runs.items.length > 0 && (
        <div className="toolbar">
          <label className="field field-inline">
            <span>Saved run</span>
            <select value={runId} onChange={(event) => setRunId(event.target.value)}>
              {runs.items.map((item) => (
                <option key={item.run_id} value={item.run_id}>
                  {formatRunLabel(item)}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
      <Tabs
        tabs={[
          { id: "results", label: "Results", icon: BarChart3 },
          { id: "samples", label: "Sample tickets", icon: ListChecks },
        ]}
        value={tab}
        onChange={setTab}
        label="Experiment views"
        idPrefix="experiments"
      />
      <div {...tabPanelProps("experiments", tab)}>{tab === "results" ? <Results run={run} loading={runs.loading} /> : <SampleTickets run={run} offline={runs.offline} />}</div>
    </div>
  );
}

function Results({ run, loading }) {
  const rows = ARMS.map((arm) => run?.arms?.find((row) => row.arm === arm)).filter(Boolean);
  const max = (key) => Math.max(...rows.map((row) => Number(row[key]) || 0));
  return (
    <div className="stack">
      {loading && (
        <p className="muted" role="status">
          Loading saved results…
        </p>
      )}
      {run && (
        <>
          <p className="muted">
            {rows[0]?.ticket_count ? `${formatNumber(rows[0].ticket_count)} ticket evaluations per design` : ""}
            {run.seeds?.length ? ` · seeds ${run.seeds.join(", ")}` : ""} · the same tickets for every design.
          </p>
          <div className="arm-grid">
            {rows.map((row) => (
              <Panel key={row.arm} className={`arm-card arm-${row.arm.toLowerCase()}`}>
                <div className="arm-card-head">
                  <span className={`arm-badge arm-${row.arm.toLowerCase()}`}>{row.arm}</span>
                  <b>{row.arm_description}</b>
                </div>
                <dl className="arm-metrics">
                  {experimentMetrics.map((metric) => (
                    <div key={metric.key}>
                      <dt>
                        {METRIC_TERMS[metric.key] ? <Term id={METRIC_TERMS[metric.key]}>{metric.label}</Term> : metric.label}
                        <Tag tone={KIND_TAG[metric.kind].tone}>{KIND_TAG[metric.kind].label}</Tag>
                      </dt>
                      <dd>
                        {metric.format(row[metric.key])}
                        {["network_bytes_mean", "wall_time_mean_s"].includes(metric.key) && (
                          <span className="bar" aria-hidden="true">
                            <i style={{ width: barWidth(row[metric.key], max(metric.key)) }} />
                          </span>
                        )}
                      </dd>
                    </div>
                  ))}
                </dl>
              </Panel>
            ))}
          </div>
          <Panel>
            <SectionTitle title="Side by side" detail="Higher is better for the scores; lower is better for time, data and rollbacks." level={3} />
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Design</th>
                    {experimentMetrics.map((metric) => (
                      <th scope="col" key={metric.key}>
                        {metric.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.arm}>
                      <th scope="row">
                        <span className={`arm-badge arm-${row.arm.toLowerCase()}`}>{row.arm}</span> {row.arm_description}
                      </th>
                      {experimentMetrics.map((metric) => (
                        <td key={metric.key}>{metric.format(row[metric.key])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted small">{run.measurement_note}</p>
            <p className="muted small">
              Known limitation: the synthetic tickets contain the severity word, so severity accuracy is 1.0 for every design. Duplicates found counts tickets whose known duplicate is in the first
              five suggestions.
            </p>
          </Panel>
        </>
      )}
      <Panel>
        <SectionTitle title="The four designs" detail={<>A0–A3 are four ways to organise the same work, not four agents (<Term id="arms">A0–A3</Term>).</>} />
        <div className="arm-grid">
          {armProcesses.map((process) => (
            <div key={process.id} className={`arm-process arm-${process.id.toLowerCase()}`}>
              <div className="arm-card-head">
                <span className={`arm-badge arm-${process.id.toLowerCase()}`}>{process.id}</span>
                <b>{process.name}</b>
              </div>
              <p className="muted small">{process.description}</p>
              <ol className="arm-steps">
                {process.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <small className="muted">{process.note}</small>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function SampleTickets({ run, offline }) {
  const [severity, setSeverity] = useState("all");
  const [state, setState] = useState({ data: null, loading: false, error: "" });
  const [selectedKey, setSelectedKey] = useState("");
  const [arm, setArm] = useState("A3");

  useEffect(() => {
    if (!run) return undefined;
    let active = true;
    setState({ data: null, loading: true, error: "" });
    api
      .evalHistory({ runId: run.run_id, severity: severity === "all" ? "Low,Medium,High,Critical" : severity })
      .then((data) => {
        if (!active) return;
        setState({ data, loading: false, error: "" });
        setSelectedKey((current) => (data.items.some((item) => `${item.seed}:${item.ticket_id}` === current) ? current : data.items[0] ? `${data.items[0].seed}:${data.items[0].ticket_id}` : ""));
      })
      .catch((err) => active && setState({ data: null, loading: false, error: err.message }));
    return () => {
      active = false;
    };
  }, [run, severity]);

  const selected = useMemo(() => state.data?.items.find((item) => `${item.seed}:${item.ticket_id}` === selectedKey), [state.data, selectedKey]);
  const armData = selected?.arms?.[arm];
  if (offline) return <EmptyState icon={FlaskConical} title="Sample tickets need the backend">They come from the saved evaluation run.</EmptyState>;
  if (!run) return null;

  return (
    <div className="stack">
      <div className="toolbar">
        <label className="field field-inline">
          <span>Severity</span>
          <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
            <option value="all">All severities</option>
            {["Low", "Medium", "High", "Critical"].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        {state.data && (
          <span className="muted small">
            Showing {state.data.total} of {state.data.matching_total} synthetic tickets (a severity-balanced sample of at most 50).
          </span>
        )}
      </div>
      {state.loading && (
        <p className="muted" role="status">
          Loading sample tickets…
        </p>
      )}
      {state.error && <Notice tone="bad" title="Sample tickets could not be loaded">{state.error}</Notice>}
      {state.data && (
        <div className="split">
          <Panel className="list-panel">
            <ul className="plain-list saved-list">
              {state.data.items.map((item) => {
                const key = `${item.seed}:${item.ticket_id}`;
                return (
                  <li key={key}>
                    <button type="button" className={`list-button ${key === selectedKey ? "is-selected" : ""}`} aria-pressed={key === selectedKey} onClick={() => setSelectedKey(key)}>
                      <span>
                        <b>
                          {item.ticket_id} <small>seed {item.seed}</small>
                        </b>
                        <small>{item.title}</small>
                      </span>
                      <Severity value={item.severity} />
                    </button>
                  </li>
                );
              })}
            </ul>
          </Panel>
          {selected && (
            <Panel className="detail-panel">
              <p className="eyebrow">
                Seed {selected.seed} · {selected.component || "synthetic"}
                {selected.created_at ? ` · ${formatTime(selected.created_at, { date: true, seconds: false })}` : ""}
              </p>
              <h2>{selected.title || selected.ticket_id}</h2>
              <blockquote className="original-text">{selected.body || "The original text is not available for this run."}</blockquote>
              {selected.duplicate_of && <p className="muted">Known duplicate of {selected.duplicate_of}.</p>}
              <label className="field field-inline">
                <span>Design</span>
                <select value={arm} onChange={(event) => setArm(event.target.value)}>
                  {ARMS.filter((value) => selected.arms[value]).map((value) => (
                    <option key={value} value={value}>
                      {value} · {selected.arms[value].arm_description}
                    </option>
                  ))}
                </select>
              </label>
              {armData && (
                <>
                  <dl className="facts">
                    <div>
                      <dt>Predicted severity</dt>
                      <dd>
                        <Severity value={armData.severity_predicted} /> {formatNumber(armData.severity_confidence * 100, 1)}% confidence
                      </dd>
                    </div>
                    <div>
                      <dt>Deployment (simulated)</dt>
                      <dd>
                        {armData.deployment_success ? (
                          <span className="text-ok">
                            <CircleCheck size={14} aria-hidden="true" /> succeeded
                          </span>
                        ) : (
                          <span className="text-bad">
                            <CircleX size={14} aria-hidden="true" /> failed
                          </span>
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>Lead time (simulated)</dt>
                      <dd>{formatNumber(armData.lead_time_hours, 2)} h</dd>
                    </div>
                    <div>
                      <dt>Data and messages</dt>
                      <dd>
                        {formatBytes(armData.network_bytes)} · {armData.messages} messages
                      </dd>
                    </div>
                    {armData.review_decision !== "not_required" && (
                      <div>
                        <dt>Synthetic review</dt>
                        <dd>
                          {armData.review_decision}: {armData.review_note}
                        </dd>
                      </div>
                    )}
                  </dl>
                  <ol className="plain-numbered eval-stages">
                    {armData.stages.map((stage) => (
                      <li key={stage.stage}>
                        <b>{stage.stage}</b> {formatNumber(stage.wall_time_seconds * 1000, 3)} ms · {formatBytes(stage.network_bytes)} · {stage.messages} messages
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </Panel>
          )}
        </div>
      )}
    </div>
  );
}
