import { useEffect, useMemo, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, Copy, Download, Gauge, GitBranch, GitPullRequest, Timer, TrendingDown, Users } from "lucide-react";
import { api } from "../api";
import ExportDialog from "../components/ExportDialog";
import MonitoringBoard from "../components/MonitoringBoard";
import Term from "../components/Term";
import { Heading, Metric, Notice, Panel, SectionTitle, SourceBadge } from "../components/Primitives";
import { agentMetricsExample, deliveryTrend, doraExample } from "../data/reportExamples.js";
import { makeScenario, scenarioRelease } from "../data/monitoringScenario.js";
import { toCsv } from "../lib/exportFile.js";
import { barWidth, formatDuration, formatNumber } from "../lib/format.js";
import { mobileCostModel, REPORT_INPUTS } from "../lib/mobileTrip.js";
import { normalizeTelemetry } from "../lib/telemetry.js";

const DORA_ICONS = { "deploy-frequency": GitPullRequest, "lead-time": Timer, "change-failure": TrendingDown, recovery: Activity, rework: GitBranch };
const AGENT_ICONS = { "triage-accuracy": Activity, "duplicate-recall": Copy, "token-cost": Gauge, "human-override": Users };

export default function MonitoringPage({ workspace, onNavigate }) {
  const { policy, mode, upsert, subscribe, records } = workspace;
  const [scenario, setScenario] = useState("flash_sale");
  const [telemetry, setTelemetry] = useState({ data: null, source: "replay" });
  const [incoming, setIncoming] = useState(null);
  const [exportData, setExportData] = useState(null);
  const [strategy, setStrategy] = useState("mobile");
  const pending = useRef(false);
  const model = useMemo(() => mobileCostModel(REPORT_INPUTS, policy), [policy]);

  // Live (backend-simulated) telemetry, or the same scenario generated offline.
  useEffect(() => {
    let active = true;
    api
      .telemetry({ scenario, seed: 42 })
      .then((raw) => active && setTelemetry({ data: normalizeTelemetry(raw), source: "simulated" }))
      .catch(() => active && setTelemetry({ data: normalizeTelemetry(makeScenario({ scenario, seed: 42, policy })), source: "replay" }));
    return () => {
      active = false;
    };
  }, [scenario, mode, policy]);

  // A follow-up ticket opened elsewhere (e.g. by the monitoring stage of a run) plays on the board.
  useEffect(
    () =>
      subscribe((event) => {
        if (event?.type === "ticket.follow_up" && !pending.current) setIncoming({ ...event, key: Date.now() });
      }),
    [subscribe],
  );

  async function createTicket(anomaly) {
    if (telemetry.source !== "simulated" || mode !== "live") {
      // Replay: nothing is created; the board says "(simulated)".
      return { ticket_id: "TCK-1043", simulated: true };
    }
    pending.current = true;
    try {
      return upsert(await api.ticketFromAnomaly(anomaly.anomaly_id));
    } finally {
      pending.current = false;
    }
  }

  const release = records.map((record) => record.agent_outputs?.deployment).find((output) => Number.isFinite(Number(output?.risk_score))) || scenarioRelease;
  const mobile = strategy === "mobile";
  const chosen = mobile ? model.mobile : model.static;

  function exportCsv() {
    const rows = [["day", "deployments", "lead_time_index", "change_failure_index"], ...deliveryTrend.map((point) => [point.day, point.deploys, point.lead, point.failure])];
    setExportData({ content: toCsv(rows), type: "text/csv;charset=utf-8", filename: "t2d-mas-delivery-example.csv", description: `${deliveryTrend.length} days of illustrative delivery data (not measured).` });
  }

  return (
    <div className="page">
      {exportData && <ExportDialog {...exportData} onClose={() => setExportData(null)} />}
      <Heading
        eyebrow="Monitoring"
        title="Is the release healthy, and how does an alert become a ticket?"
        what="An hour of telemetry played back minute by minute, the alert it raises, and the canary release of the fix."
        why="Monitoring closes the loop: problems after a release go straight back to Triage as new tickets."
        action={
          <label className="field field-inline">
            <span>Scenario</span>
            <select value={scenario} onChange={(event) => setScenario(event.target.value)}>
              <option value="flash_sale">Flash sale (incident)</option>
              <option value="normal">Normal hour</option>
            </select>
          </label>
        }
      />
      {telemetry.source === "replay" && (
        <Notice tone="warn" title="Offline scenario">
          The backend is not reachable, so this hour is generated in the browser with the same seeded recipe. Follow-up tickets are simulated.
        </Notice>
      )}

      <Panel>
        {telemetry.data && (
          <MonitoringBoard
            key={`${telemetry.source}-${scenario}`}
            telemetry={telemetry.data}
            source={telemetry.source}
            release={release}
            policy={policy}
            onCreateTicket={createTicket}
            incomingFollowUp={incoming}
            onOpenTickets={() => onNavigate("tickets")}
          />
        )}
      </Panel>

      <SectionTitle title="Delivery report" detail="Illustrative numbers from the report's idea, not measured by this prototype." action={<SourceBadge source="replay" label="Illustrative sample" />} />
      <div className="metric-grid">
        {doraExample.map((item) => (
          <Metric key={item.id} label={item.label} value={item.value} unit={item.unit} change={item.change} goodDirection={item.goodDirection} note={item.note} icon={DORA_ICONS[item.id]} />
        ))}
      </div>
      <p className="muted small">
        <Term id="dora">DORA metrics</Term> measure delivery speed and stability. <Term id="recovery-time">Recovery time</Term> is how fast service returns after a failed deploy.
      </p>

      <div className="split">
        <Panel>
          <SectionTitle
            title="Delivery trend (30 days)"
            level={3}
            action={
              <button type="button" className="button button-small" onClick={exportCsv}>
                <Download size={15} aria-hidden="true" />
                CSV
              </button>
            }
          />
          <ul className="chart-legend" aria-hidden="true">
            <li>
              <span className="swatch swatch-1" /> Deployments per day
            </li>
            <li>
              <span className="swatch swatch-2" /> Lead time index
            </li>
            <li>
              <span className="swatch swatch-3" /> Failure index
            </li>
          </ul>
          <div className="chart chart-small" role="img" aria-label="Illustrative line chart: deployments per day rise slowly while the lead time and failure indices fall over 30 days.">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={deliveryTrend} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" strokeDasharray="3 5" vertical={false} />
                <XAxis dataKey="day" tickLine={false} axisLine={false} interval={4} tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--text)" }} />
                <Line type="monotone" dataKey="deploys" name="Deployments" stroke="var(--series-1)" strokeWidth={2.2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="lead" name="Lead time index" stroke="var(--series-2)" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="failure" name="Failure index" stroke="var(--series-3)" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel>
          <SectionTitle title="Static pull vs mobile agent" detail="Same incident window, six nodes (report cost model)." level={3} />
          <div className="segmented" role="group" aria-label="Strategy">
            {[
              ["mobile", "Mobile agent"],
              ["static", "Static pull"],
            ].map(([value, label]) => (
              <button key={value} type="button" className={`segment ${strategy === value ? "is-selected" : ""}`} aria-pressed={strategy === value} onClick={() => setStrategy(value)}>
                {label}
              </button>
            ))}
          </div>
          <dl className="compare">
            <div>
              <dt>Time</dt>
              <dd>
                <span className="bar">
                  <i className={mobile ? "is-good" : "is-bad"} style={{ width: barWidth(chosen.seconds, model.static.seconds) }} />
                </span>
                {formatDuration(chosen.seconds)}
              </dd>
            </div>
            <div>
              <dt>Data moved</dt>
              <dd>
                <span className="bar">
                  <i className={mobile ? "is-good" : "is-bad"} style={{ width: barWidth(chosen.mb, model.static.mb) }} />
                </span>
                {formatNumber(chosen.mb)} MB
              </dd>
            </div>
          </dl>
          <p className="muted small">
            {mobile
              ? `${formatNumber(model.savedPercent, 2)}% fewer bytes and about ${Math.floor(model.speedup)}× faster; raw logs and personal data stay on the nodes.`
              : "Every raw log, personal data included, travels to one server before analysis starts."}{" "}
            <button type="button" className="link-button" onClick={() => onNavigate("agents")}>
              Watch the trip
            </button>
          </p>
          <SectionTitle title="Agent system signals" level={3} />
          <div className="metric-grid metric-grid-small">
            {agentMetricsExample.map((item) => (
              <Metric key={item.id} label={item.label} value={item.value} change={item.change} goodDirection={item.goodDirection} icon={AGENT_ICONS[item.id]} />
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
