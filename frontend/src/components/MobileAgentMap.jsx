// The Scout-Log trip: an orchestrator hub and six data nodes. In mobile mode a signed bundle
// goes out and only an aggregate comes back; in static mode every raw log streams to the hub.
// Model trips play phase by phase; live trips follow each node's real response.
import { useEffect, useMemo } from "react";
import { CircleCheck, CircleX, KeyRound, LoaderCircle, Play, Server } from "lucide-react";
import { formatBytes, formatDuration, formatNumber } from "../lib/format.js";
import { ringPositions, tripSteps, tripTotals } from "../lib/mobileTrip.js";
import { useCountUp } from "../hooks/useCountUp";
import { useStepPlayer } from "../hooks/useStepPlayer";
import PlayerControls from "./PlayerControls";
import Term from "./Term";
import { SourceBadge } from "./Primitives";

const WIDTH = 640;
const HEIGHT = 440;
const HUB = { x: 320, y: 220 };
const RING = ringPositions(6, HUB.x, HUB.y, 140);

/** Sizes as the report writes them: whole megabytes ("1,365 MB"), or bytes/KB for small live trips. */
const tripBytes = (bytes) => (bytes >= 1e6 ? `${formatNumber(bytes / 1e6, bytes % 1e6 ? 1 : 0)} MB` : formatBytes(bytes));

/** A point moved from `a` towards `b` by `distance`. */
function towards(a, b, distance) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy) || 1;
  return { x: a.x + (dx / length) * distance, y: a.y + (dy / length) * distance };
}

/** What each node shows at a model phase or for a live response. */
function nodeVisual(node, phaseId, mode, live) {
  if (live) return { travelling: "outbound", returned: "inbound", failed: "failed" }[node.status] || "idle";
  if (mode === "static") return phaseId === "pull" ? "streaming" : "pulled";
  return { sign: "idle", dispatch: "outbound", execute: "running", return: "inbound", done: "done" }[phaseId] || "idle";
}

function Traveller({ from, to, label, className, delay = 0 }) {
  const start = towards(from, to, 34);
  const end = towards(to, from, 30);
  const width = label.length * 5.4 + 14;
  return (
    <g className={`trip-packet travel ${className}`} style={{ "--x1": `${start.x}px`, "--y1": `${start.y}px`, "--x2": `${end.x}px`, "--y2": `${end.y}px`, "--delay": `${delay}ms`, "--travel-ms": "900ms" }}>
      <rect x={-width / 2} y={-9} width={width} height={18} rx={4} />
      <text y={3.5}>{label}</text>
    </g>
  );
}

export default function MobileAgentMap({ trip, model, source = "model", mode = "mobile", onModeChange, onInvestigate, investigating = false, title = "Scout-Log trip", compact = false }) {
  const live = trip?.source === "live";
  const steps = useMemo(() => tripSteps(model, mode), [model, mode]);
  const player = useStepPlayer(steps, { autoPlay: false });
  const phase = live ? null : steps[player.index];
  const { seek } = player;

  // A new mode starts its own story from the first phase.
  useEffect(() => {
    seek(0);
  }, [mode, seek]);

  const nodes = trip?.nodes || [];
  const totals = tripTotals(trip);
  const counterTarget = live ? totals.bytesMoved : (phase?.counterMb ?? 0);
  const counter = useCountUp(counterTarget, { durationMs: live ? 600 : phase?.durationMs || 900 });
  const counterText = live ? formatBytes(counter) : `${formatNumber(counter)} MB`;
  const secondsText = live ? null : `≈ ${formatDuration(phase?.seconds ?? 0)} (simulated)`;
  const caption = live
    ? investigating
      ? `Scout-Log is visiting the nodes: ${totals.returned + totals.failed} of ${nodes.length} answered.`
      : `${totals.returned} of ${nodes.length} nodes answered${totals.failed ? `, ${totals.failed} failed` : ""}. ${tripBytes(totals.bytesMoved)} moved; ${tripBytes(totals.bytesKept)} of raw logs stayed on the nodes.`
    : phase?.caption;

  return (
    <figure className={`trip ${compact ? "is-compact" : ""}`}>
      <div className="flow-head">
        <h3>{title}</h3>
        <SourceBadge source={source} />
      </div>
      {onModeChange && (
        <div className="segmented" role="group" aria-label="Investigation strategy">
          {[
            ["mobile", "Mobile agent"],
            ["static", "Static pull"],
          ].map(([value, label]) => (
            <button key={value} type="button" className={`segment ${mode === value ? "is-selected" : ""}`} aria-pressed={mode === value} onClick={() => onModeChange(value)}>
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="trip-stage">
        <svg className="trip-svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`${title}. ${caption || ""}`}>
          {RING.map((point, index) => {
            const node = nodes[index];
            const visual = node ? nodeVisual(node, phase?.id, mode, live) : "idle";
            return <line key={index} className={`trip-link ${visual === "streaming" ? "is-streaming" : ""} ${visual === "pulled" ? "is-pulled" : ""}`} x1={HUB.x} y1={HUB.y} x2={point.x} y2={point.y} />;
          })}

          <g className={`trip-hub ${phase?.id === "sign" ? "is-signing" : ""}`} transform={`translate(${HUB.x} ${HUB.y})`}>
            <rect x={-62} y={-24} width={124} height={48} rx={12} />
            <KeyRound x={-52} y={-9} width={18} height={18} aria-hidden="true" />
            <text x={8} y={-3}>
              Orchestrator
            </text>
            <text className="trip-hub-counter" x={8} y={13}>
              {counterText}
            </text>
          </g>

          {RING.map((point, index) => {
            const node = nodes[index];
            if (!node) return null;
            const visual = nodeVisual(node, phase?.id, mode, live);
            const stays = mode === "mobile" && ["running", "inbound", "done"].includes(visual) && !live;
            const Icon = visual === "failed" ? CircleX : visual === "done" || visual === "inbound" ? CircleCheck : visual === "outbound" && live ? LoaderCircle : Server;
            return (
              <g key={node.node_id}>
                <g className={`trip-node is-${visual}`} transform={`translate(${point.x} ${point.y})`}>
                  <rect x={-70} y={-20} width={140} height={40} rx={10} />
                  <Icon x={-62} y={-8} width={16} height={16} aria-hidden="true" className={visual === "outbound" && live ? "trip-spinner" : undefined} />
                  <text className="trip-node-id" x={-40} y={-3}>
                    {node.node_id}
                  </text>
                  <text className="trip-node-service" x={-40} y={11}>
                    {node.service}
                  </text>
                  {stays && (
                    <g className="trip-stay" transform="translate(0 33)">
                      <rect x={-62} y={-9} width={124} height={18} rx={9} />
                      <text y={3.5}>{tripBytes(node.logBytes)} stays here</text>
                    </g>
                  )}
                  {visual === "streaming" && (
                    <g className="trip-stay is-leaving" transform="translate(0 33)">
                      <rect x={-62} y={-9} width={124} height={18} rx={9} />
                      <text y={3.5}>{tripBytes(node.logBytes)} sent</text>
                    </g>
                  )}
                  {visual === "failed" && (
                    <text className="trip-error" y={36}>
                      {(node.error || "No response").slice(0, 34)}
                    </text>
                  )}
                </g>
                {/* key={phase} restarts the CSS travel animation for every phase. */}
                <g key={`${phase?.id || node.status}-${mode}`}>
                  {visual === "outbound" && <Traveller from={HUB} to={point} label="signed bundle" className="is-bundle" delay={index * 80} />}
                  {visual === "inbound" && <Traveller from={point} to={HUB} label="aggregate" className="is-aggregate" delay={live ? 0 : index * 80} />}
                </g>
              </g>
            );
          })}
        </svg>
      </div>
      <p className="flow-caption" aria-live={player.playing ? "off" : "polite"}>
        {live ? caption : `${phase?.label}: ${caption}`} {secondsText && <span className="muted">· {secondsText}</span>}
      </p>
      {!live && <PlayerControls player={player} label="Trip controls" stepName="Phase" scrub={false} />}
      <div className="button-row">
        {!live && player.index === 0 && !player.playing && (
          <button type="button" className="button button-primary" onClick={player.play}>
            <Play size={15} aria-hidden="true" />
            Play the trip
          </button>
        )}
        {onInvestigate && (
          <button type="button" className="button" onClick={onInvestigate} disabled={investigating}>
            <Server size={15} aria-hidden="true" />
            {investigating ? "Visiting the nodes…" : "Investigate on the real nodes"}
          </button>
        )}
      </div>
      {!compact && (
        <dl className="trip-summary">
          <div>
            <dt>Bytes saved</dt>
            <dd>{formatNumber(model.savedPercent, 2)}% fewer</dd>
          </div>
          <div>
            <dt>Speed</dt>
            <dd>≈{Math.floor(model.speedup)}× faster</dd>
          </div>
          <div>
            <dt>
              <Term id="break-even">Break-even</Term>
            </dt>
            <dd>{formatNumber(model.breakEvenMb)} MB per node</dd>
          </div>
          <div>
            <dt>Migrate rule</dt>
            <dd>above {formatNumber(model.migrateThresholdMb)} MB per node</dd>
          </div>
        </dl>
      )}
      <ol className="trip-log" aria-label="What happened at each node">
        {nodes.map((node) => (
          <li key={node.node_id} className={`is-${node.status}`}>
            <b>
              {node.node_id} · {node.service}
            </b>{" "}
            {node.status === "failed"
              ? `— failed: ${node.error || "no response"}`
              : node.status === "travelling"
                ? "— bundle on its way…"
                : node.mode === "node_exporter"
                  ? `— too little data to move the agent (rule says no), so the node's exporter answered; ${formatBytes(node.bytesSent + node.bytesReturned)} moved.`
                  : mode === "static" && !live
                    ? `— sent all ${tripBytes(node.logBytes)} of raw logs to the hub.`
                    : `— agent ran on the node; ${tripBytes(node.bytesSent)} out, ${tripBytes(node.bytesReturned)} back; ${tripBytes(node.logBytes)} of raw logs stayed.`}
          </li>
        ))}
      </ol>
    </figure>
  );
}
