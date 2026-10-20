// Telemetry playback: a metric grows minute by minute against its SLO, an anomaly pulses and
// raises an alert card, and "Open a follow-up ticket" flies an envelope into Triage.
// A canary bar shows how the fix is released in steps.
import { useEffect, useMemo, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowRight, BellRing, CircleCheck, CircleX, Mail, ShieldCheck, Ticket } from "lucide-react";
import { canaryAt, describeAnomaly, METRICS, metricInfo, pivotSeries, sloStatus } from "../lib/telemetry.js";
import { canaryAllowed, DEFAULT_POLICY } from "../lib/policy.js";
import { formatNumber } from "../lib/format.js";
import { stages } from "../lib/workflow.js";
import { useStepPlayer } from "../hooks/useStepPlayer";
import PlayerControls from "./PlayerControls";
import Term from "./Term";
import { SourceBadge, Tabs } from "./Primitives";

const SERIES_COLOURS = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

function AnomalyDot({ cx, cy }) {
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;
  return (
    <g>
      <circle className="anomaly-ring" cx={cx} cy={cy} r={7} />
      <circle className="anomaly-dot" cx={cx} cy={cy} r={5} />
    </g>
  );
}

export default function MonitoringBoard({ telemetry, source = "replay", release, policy = DEFAULT_POLICY, onCreateTicket, incomingFollowUp, onOpenTickets }) {
  const minutes = useMemo(() => Array.from({ length: telemetry?.minutes || 0 }, (_, minute) => minute), [telemetry]);
  const player = useStepPlayer(minutes, { baseMs: 250 });
  const cursor = player.index;
  const [metric, setMetric] = useState("latency_p95_ms");
  const firstAnomaly = telemetry?.anomalies?.[0];
  const [service, setService] = useState(firstAnomaly?.service || telemetry?.services?.[0]?.service || "");
  const [created, setCreated] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [flight, setFlight] = useState(null);
  const boardRef = useRef(null);
  const buttonRef = useRef(null);
  const triageRef = useRef(null);
  const { reduced, seek } = player;

  // New telemetry (another scenario): start again on the service with the first anomaly.
  useEffect(() => {
    setService(telemetry?.anomalies?.[0]?.service || telemetry?.services?.[0]?.service || "");
    setCreated(null);
    setFlight(null);
    // With reduced motion the whole hour is drawn at once; the slider still steps.
    seek(reduced ? Math.max(0, (telemetry?.minutes || 1) - 1) : 0);
  }, [telemetry, reduced, seek]);

  const info = metricInfo(metric);
  const current = telemetry?.services?.find((item) => item.service === service) || telemetry?.services?.[0];
  const rows = useMemo(() => (telemetry ? pivotSeries(telemetry, metric, cursor) : []), [telemetry, metric, cursor]);
  const slo = current?.slo?.[metric] ?? null;
  // A fixed y axis (the whole hour, and the SLO) so the chart does not rescale while it plays.
  const yMax = useMemo(() => {
    const values = (current?.series?.[metric] || []).filter((value) => Number.isFinite(value));
    const top = Math.max(0, ...values, slo ?? 0);
    return top ? top * 1.1 : 1;
  }, [current, metric, slo]);
  const revealed = (telemetry?.anomalies || []).filter((item) => item.start_minute <= cursor);
  const alert = revealed[0] || null;
  const steps = telemetry?.canarySteps || [];
  const canary = canaryAt(steps, cursor);
  const rolledBack = steps.some((step) => step.minute <= cursor && step.status !== "healthy");
  const risk = release?.risk_score;
  const autonomousCanary = Number.isFinite(risk) ? canaryAllowed(risk, policy) : null;

  // Play the envelope from the alert card into the Triage chip.
  function fly() {
    const box = boardRef.current?.getBoundingClientRect();
    const from = buttonRef.current?.getBoundingClientRect();
    const to = triageRef.current?.getBoundingClientRect();
    if (!box || !from || !to) return;
    setFlight({
      key: Date.now(),
      x1: from.left + from.width / 2 - box.left,
      y1: from.top + from.height / 2 - box.top,
      x2: to.left + to.width / 2 - box.left,
      y2: to.top + to.height / 2 - box.top,
    });
  }

  async function openTicket() {
    if (!alert || sending) return;
    setSending(true);
    setError("");
    fly();
    try {
      const ticket = await onCreateTicket?.(alert);
      setCreated(ticket ? { ticketId: ticket.ticket_id, simulated: Boolean(ticket.simulated) } : null);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  // A follow-up opened elsewhere (SSE ticket.follow_up) plays the same sequence without a click.
  useEffect(() => {
    if (!incomingFollowUp?.ticket_id) return;
    setCreated({ ticketId: incomingFollowUp.ticket_id, simulated: false });
    fly();
  }, [incomingFollowUp]);

  if (!telemetry || !telemetry.minutes) return null;

  return (
    <figure className="monitor" ref={boardRef}>
      <div className="flow-head">
        <h3>Release health, minute by minute</h3>
        <SourceBadge source={source} />
      </div>
      <div className="monitor-controls">
        <div className="segmented" role="group" aria-label="Service">
          {telemetry.services.map((item, index) => (
            <button key={item.service} type="button" className={`segment ${item.service === current?.service ? "is-selected" : ""}`} aria-pressed={item.service === current?.service} onClick={() => setService(item.service)}>
              <span className={`swatch swatch-${index + 1}`} aria-hidden="true" />
              {item.service}
            </button>
          ))}
        </div>
        <Tabs tabs={METRICS.map((item) => ({ id: item.id, label: item.label }))} value={metric} onChange={setMetric} label="Metric" idPrefix="metric" />
      </div>

      <div className="chart" role="img" aria-label={`${info.label} of ${current?.service} for minutes 0 to ${cursor}${slo !== null ? `, SLO ${info.format(slo)}` : ""}. ${revealed.length ? describeAnomaly(revealed[0]) : "No anomaly so far."}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 12, right: 18, left: 4, bottom: 4 }}>
            <CartesianGrid stroke="var(--grid)" strokeDasharray="3 5" vertical={false} />
            <XAxis dataKey="minute" type="number" domain={[0, telemetry.minutes - 1]} tickCount={7} tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} label={{ value: "minute", position: "insideBottomRight", offset: -2, fill: "var(--text-muted)", fontSize: 11 }} />
            <YAxis width={56} domain={[0, yMax]} tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(value) => (metric === "error_rate" ? `${formatNumber(value * 100, 0)}%` : formatNumber(value))} />
            <Tooltip formatter={(value) => info.format(value)} labelFormatter={(value) => `Minute ${value}`} contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--text)" }} />
            {telemetry.scenario === "flash_sale" && <ReferenceArea x1={18} x2={36} fill="var(--warn-soft)" fillOpacity={0.5} label={{ value: "flash sale", position: "insideTop", fill: "var(--text-muted)", fontSize: 11 }} />}
            {slo !== null && <ReferenceLine y={slo} ifOverflow="extendDomain" stroke="var(--bad)" strokeDasharray="6 4" label={{ value: `SLO ${info.format(slo)}`, position: "insideTopLeft", fill: "var(--bad)", fontSize: 11 }} />}
            <Line type="monotone" dataKey={current?.service} stroke={SERIES_COLOURS[telemetry.services.indexOf(current) % 3]} strokeWidth={2.4} dot={false} isAnimationActive={false} connectNulls={false} />
            {revealed
              .filter((item) => item.service === current?.service && item.metric === metric)
              .map((item) => (
                <ReferenceDot key={item.anomaly_id} x={item.peak_minute <= cursor ? item.peak_minute : item.start_minute} y={item.peak_minute <= cursor ? item.peak_value : current.series[metric][item.start_minute]} shape={AnomalyDot} />
              ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <PlayerControls player={player} label="Telemetry playback" stepName="Minute" valueText={`Minute ${cursor} of ${telemetry.minutes - 1}`} />

      <ul className="service-status" aria-label={`Status at minute ${cursor}`}>
        {telemetry.services.map((item) => {
          const value = item.series[metric]?.[cursor];
          const status = sloStatus(value, item.slo?.[metric] ?? null);
          const Icon = status.state === "breach" ? CircleX : CircleCheck;
          return (
            <li key={item.service} className={`status-${status.state}`}>
              {status.state !== "unknown" && <Icon size={15} aria-hidden="true" />}
              <b>{item.service}</b> {info.format(value)} · {status.label}
            </li>
          );
        })}
      </ul>

      <div className="monitor-loop">
        {alert ? (
          <div className="alert-card" role="status">
            <BellRing size={18} aria-hidden="true" />
            <div>
              <b>
                <Term id="anomaly">Anomaly</Term> at minute {alert.start_minute}
              </b>
              <p>{describeAnomaly(alert)}</p>
              <button ref={buttonRef} type="button" className="button button-primary" onClick={openTicket} disabled={sending || Boolean(created)}>
                <Ticket size={15} aria-hidden="true" />
                {created ? "Follow-up ticket opened" : sending ? "Opening…" : "Open a follow-up ticket"}
              </button>
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="alert-card is-quiet">
            <ShieldCheck size={18} aria-hidden="true" />
            <div>
              <b>No anomaly yet</b>
              <p>Every metric is within its SLO up to minute {cursor}. Play on to see what happens.</p>
            </div>
          </div>
        )}
        <div className="mini-strip" aria-label="Where a follow-up ticket enters the pipeline">
          {stages.map((stage) => (
            <span key={stage.id} ref={stage.id === "triage" ? triageRef : undefined} className={`mini-stage ${created && (stage.id === "intake" || stage.id === "triage") ? "is-hit" : ""}`}>
              {stage.name}
            </span>
          ))}
          {created && (
            <p className="mini-result" role="status">
              <b>{created.ticketId}</b> created{created.simulated ? " (simulated)" : ""} → Feedback capture → Triage.{" "}
              {onOpenTickets && !created.simulated && (
                <button type="button" className="link-button" onClick={onOpenTickets}>
                  See it on the board <ArrowRight size={14} aria-hidden="true" />
                </button>
              )}
            </p>
          )}
        </div>
        {flight && (
          <div key={flight.key} className="monitor-flight travel" style={{ "--x1": `${flight.x1}px`, "--y1": `${flight.y1}px`, "--x2": `${flight.x2}px`, "--y2": `${flight.y2}px`, "--travel-ms": "900ms" }} aria-hidden="true">
            <span>
              <Mail size={14} /> ticket
            </span>
          </div>
        )}
      </div>

      <div className="canary" aria-label="Canary release">
        <div className="canary-head">
          <b>
            <Term id="canary">Canary release</Term>
          </b>
          <span>
            {steps.length
              ? rolledBack
                ? "Rolled back to 0%: a step broke the SLO."
                : `${canary.percent}% of users on the new version`
              : "No release in this hour."}
          </span>
        </div>
        <div className="canary-track">
          <div className={`canary-fill ${rolledBack ? "is-rolled-back" : ""}`} style={{ width: `${rolledBack ? 0 : canary.percent}%` }} />
          {steps.map((step) => (
            <span key={step.minute} className={`canary-tick ${step.minute <= cursor ? "is-reached" : ""}`} style={{ left: `${step.percent}%` }}>
              {step.percent}%
            </span>
          ))}
        </div>
        {steps.length > 0 && (
          <ol className="canary-steps">
            {steps.map((step, index) => (
              <li key={step.minute} className={step.minute <= cursor ? "is-reached" : ""}>
                {step.minute <= cursor ? (step.status === "healthy" ? <CircleCheck size={14} aria-hidden="true" /> : <CircleX size={14} aria-hidden="true" />) : <span className="dot" aria-hidden="true" />}
                <b>{step.percent}%</b> at minute {step.minute}
                {index === 0 &&
                  ` — ${autonomousCanary === false ? `needs a human (risk ${formatNumber(risk, 2)} > ${formatNumber(policy.canary.risk_max, 2)})` : `autonomous if risk ≤ ${formatNumber(policy.canary.risk_max, 2)}${Number.isFinite(risk) ? ` (this run: ${formatNumber(risk, 2)})` : ""}`}`}
                {step.needsHuman && " — full release needs a human"}
                {step.minute <= cursor && step.status !== "healthy" && " — unhealthy, rolled back to 0%"}
              </li>
            ))}
          </ol>
        )}
      </div>
    </figure>
  );
}
