// The animated nine-stage pipeline. It draws one frame (see lib/flow.js); CSS keyframes move
// the envelopes within the frame, and `key={frame.id}` restarts them on every step.
// With reduced motion the CSS turns animations off, so each frame shows its end state.
import { useId } from "react";
import { Check, Inbox, Minus, RotateCcw, Shield, ShieldAlert, ShieldCheck, ShieldX, Smartphone, Users, Workflow, X } from "lucide-react";
import { anchorPoint, describeFrame, envelopeLine, layoutFlow } from "../lib/flow.js";
import { gates, stageIds, stages, stateLabel } from "../lib/workflow.js";
import { DEFAULT_POLICY, gateLabel } from "../lib/policy.js";
import PlayerControls from "./PlayerControls";
import { SourceBadge } from "./Primitives";

const LAYOUT = layoutFlow();
const ANCHOR_ICONS = { channels: Inbox, security: Shield, human: Users, orchestrator: Workflow };

// Gate shields sit on the connector after their stage; two gates on one connector share it.
const GATE_SPOTS = gates.map((gate) => {
  const sameStage = gates.filter((item) => item.stage === gate.stage);
  const position = sameStage.indexOf(gate) + 1;
  const from = LAYOUT.nodes[gate.stage];
  const to = LAYOUT.nodes[stageIds[stageIds.indexOf(gate.stage) + 1]];
  return { gate, x: from.x + ((to.x - from.x) * position) / (sameStage.length + 1), y: from.y };
});

const textWidth = (text, size = 10) => Math.max(28, String(text).length * size * 0.56 + 14);

function NodeIcon({ state, number }) {
  const props = { x: -9, y: -9, width: 18, height: 18, "aria-hidden": true, strokeWidth: 2.4 };
  if (state === "done") return <Check {...props} />;
  if (state === "stopped") return <X {...props} />;
  if (state === "waiting") return <ShieldAlert {...props} />;
  if (state === "revising") return <RotateCcw {...props} />;
  if (state === "skipped") return <Minus {...props} />;
  return (
    <text className="flow-node-number" y={5}>
      {number}
    </text>
  );
}

function GateShield({ spot, state, policy }) {
  const Icon = state === "passed" ? ShieldCheck : state === "stopped" ? ShieldX : state === "waiting" || state === "revising" ? ShieldAlert : Shield;
  return (
    <g className={`flow-gate ${spot.gate.conditional ? "is-conditional" : ""} ${state ? `is-${state}` : ""}`} transform={`translate(${spot.x} ${spot.y})`}>
      <title>{`${gateLabel(spot.gate.id, policy)}${spot.gate.conditional ? " (only when a rule fails)" : " (always asks a person)"}`}</title>
      {state === "waiting" && <circle className="flow-gate-ring" r={13} />}
      <circle className="flow-gate-disc" r={10} />
      <Icon x={-7} y={-7} width={14} height={14} aria-hidden="true" />
      {spot.gate.conditional && (
        <text className="flow-gate-note" y={22}>
          if risky
        </text>
      )}
    </g>
  );
}

function Badge({ x, y, text, tone = "info", className = "" }) {
  const width = textWidth(text);
  return (
    <g className={`flow-badge tone-${tone} ${className}`} transform={`translate(${x} ${y})`}>
      <rect x={-width / 2} y={-9} width={width} height={18} rx={9} />
      <text y={3.5}>{text}</text>
    </g>
  );
}

export default function PipelineFlow({ frame, source = "replay", player, title = "Ticket journey", ticketLabel = "Ticket", stepLabel, selectedStage, onSelectStage, policy = DEFAULT_POLICY }) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  if (!frame) return null;
  const receiving = new Set(frame.envelopes.map((envelope) => envelope.to));
  const usedAnchors = new Set([...frame.envelopes.flatMap((envelope) => [envelope.from, envelope.to]), ...frame.bids.map((bid) => bid.anchor)]);
  const squads = ["squad-0", "squad-1", "squad-2"].filter((id) => usedAnchors.has(id));
  const marker = LAYOUT.nodes[frame.marker?.stage] || LAYOUT.nodes.intake;
  const caption = [stepLabel || (player ? `Step ${player.index + 1} of ${player.count}` : null), frame.timeLabel, frame.caption].filter(Boolean).join(" · ");

  return (
    <figure className="flow">
      <div className="flow-head">
        <h3>{title}</h3>
        <SourceBadge source={source} />
      </div>
      <div className="flow-scroll">
        <svg className="flow-svg" viewBox={`0 0 ${LAYOUT.width} ${LAYOUT.height}`} role="img" aria-labelledby={`${uid}-title ${uid}-desc`}>
          <title id={`${uid}-title`}>{title}</title>
          <desc id={`${uid}-desc`}>{describeFrame(frame, policy)}</desc>
          <defs>
            <marker id={`${uid}-arrow`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" className="flow-arrowhead" />
            </marker>
          </defs>

          {/* Connectors: solid once the earlier stage is done, dashed while upcoming. */}
          {stages.slice(1).map((stage, index) => {
            const from = LAYOUT.nodes[stages[index].id];
            const to = LAYOUT.nodes[stage.id];
            const done = frame.stages[stages[index].id] === "done";
            return <line key={stage.id} className={`flow-link ${done ? "is-done" : ""}`} x1={from.x + 22} y1={from.y} x2={to.x - 22} y2={to.y} />;
          })}

          <path className={`flow-loop ${frame.loop ? "is-active" : ""}`} d={LAYOUT.loopPath} markerEnd={`url(#${uid}-arrow)`} />
          <text className={`flow-loop-label ${frame.loop ? "is-active" : ""}`} x={LAYOUT.loopLabel.x} y={LAYOUT.loopLabel.y}>
            Feedback loop: Monitoring → Triage
          </text>

          {GATE_SPOTS.map((spot) => (
            <GateShield key={spot.gate.id} spot={spot} state={frame.gate?.id === spot.gate.id ? frame.gate.state : null} policy={policy} />
          ))}

          {/* Supporting actors around the pipeline. */}
          {Object.entries(ANCHOR_ICONS).map(([id, Icon]) => {
            const point = LAYOUT.anchors[id];
            return (
              <g key={id} className={`flow-anchor ${receiving.has(id) ? "is-receiving" : ""} ${usedAnchors.has(id) ? "is-used" : ""}`} transform={`translate(${point.x} ${point.y})`}>
                <circle r={15} />
                <Icon x={-8} y={-8} width={16} height={16} aria-hidden="true" />
                <text className="flow-anchor-label" y={30}>
                  {point.label}
                </text>
              </g>
            );
          })}
          <g className={`flow-anchor ${receiving.has("scoutLog") ? "is-receiving" : ""} ${usedAnchors.has("scoutLog") ? "is-used" : ""}`} transform={`translate(${LAYOUT.anchors.scoutLog.x} ${LAYOUT.anchors.scoutLog.y})`}>
            <line className="flow-tether" x1={0} y1={-12} x2={0} y2={-(LAYOUT.anchors.scoutLog.y - LAYOUT.rowY - 24)} />
            <circle r={12} />
            <Smartphone x={-7} y={-7} width={14} height={14} aria-hidden="true" />
            <text className="flow-anchor-label is-side" x={18} y={4}>
              {LAYOUT.anchors.scoutLog.label}
            </text>
          </g>
          {squads.map((id) => {
            const point = LAYOUT.anchors[id];
            const bid = frame.bids.find((item) => item.anchor === id);
            return (
              <g key={id} className={`flow-squad ${bid?.winner ? "is-winner" : ""} ${receiving.has(id) ? "is-receiving" : ""}`} transform={`translate(${point.x} ${point.y})`}>
                <rect x={-46} y={-11} width={92} height={22} rx={11} />
                <text y={4}>{bid && Number.isFinite(bid.utility) ? `${point.label} · ${bid.utility.toFixed(2)}` : point.label}</text>
              </g>
            );
          })}

          {/* The nine stages. */}
          {stages.map((stage, index) => {
            const point = LAYOUT.nodes[stage.id];
            const state = frame.stages[stage.id] || "upcoming";
            return (
              <g
                key={stage.id}
                className={`flow-node state-${state} ${receiving.has(stage.id) ? "is-receiving" : ""} ${selectedStage === stage.id ? "is-selected" : ""} ${onSelectStage ? "is-clickable" : ""}`}
                transform={`translate(${point.x} ${point.y})`}
                onClick={onSelectStage ? () => onSelectStage(stage.id) : undefined}
              >
                {state === "active" && <circle className="flow-node-ring" r={22} />}
                <circle className="flow-node-disc" r={22} />
                <NodeIcon state={state} number={index + 1} />
                <text className="flow-node-name" y={40}>
                  {stage.name}
                </text>
                <text className="flow-node-state" y={54}>
                  {stateLabel[state]}
                </text>
              </g>
            );
          })}

          {/* Bids on stage nodes (the report example) sit above the bidder. */}
          {frame.bids
            .filter((bid) => LAYOUT.nodes[bid.anchor] && Number.isFinite(bid.utility))
            .map((bid) => (
              <Badge key={bid.worker} x={LAYOUT.nodes[bid.anchor].x} y={86} text={`${bid.winner ? "Winner " : "Bid "}${bid.utility.toFixed(2)}`} tone={bid.winner ? "accent" : "info"} className={bid.winner ? "is-winner" : ""} />
            ))}

          {frame.badges.map((badge) => {
            const point = anchorPoint(badge.at, LAYOUT);
            const satellite = badge.at === "scoutLog";
            // Triage's badge drops to a second row so it never overlaps its neighbours; the
            // others stay above the feedback-loop arc. Every badge stays inside the picture.
            const row = badge.at === "triage" ? 1 : 0;
            const half = textWidth(badge.text) / 2 + 4;
            const x = Math.min(LAYOUT.width - half, Math.max(half, satellite ? point.x - 82 : point.x));
            return <Badge key={`${badge.at}-${badge.text}`} x={x} y={satellite ? point.y : LAYOUT.rowY + 74 + row * 22} text={badge.text} tone={badge.tone} />;
          })}

          {/* The ticket marker glides between stages (CSS transition on transform). */}
          <g className="flow-marker" style={{ transform: `translate(${marker.x}px, ${LAYOUT.markerY}px)` }}>
            <rect x={-34} y={-9} width={68} height={18} rx={9} />
            <text y={3.5}>{frame.marker?.label || ticketLabel}</text>
          </g>

          {/* Messages: a faint trail with an arrow, and an envelope that travels along it. */}
          <g key={frame.id}>
            {frame.envelopes.map((envelope) => {
              const line = envelopeLine(envelope, LAYOUT);
              const width = textWidth(envelope.performative, 8.5);
              return (
                <g key={envelope.id}>
                  <line className="flow-trail" x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} markerEnd={`url(#${uid}-arrow)`} />
                  <g
                    className="flow-envelope travel"
                    style={{ "--x1": `${line.x1}px`, "--y1": `${line.y1}px`, "--x2": `${line.x2}px`, "--y2": `${line.y2}px`, "--delay": `${envelope.delay || 0}ms` }}
                  >
                    <rect x={-width / 2} y={-8} width={width} height={16} rx={3} />
                    <text y={3}>{envelope.performative}</text>
                  </g>
                </g>
              );
            })}
          </g>
        </svg>
      </div>
      <p className="flow-caption" aria-live={player?.playing ? "off" : "polite"}>
        {caption}
      </p>
      <ol className="visually-hidden">
        {stages.map((stage) => (
          <li key={stage.id}>
            {stage.name}: {stateLabel[frame.stages[stage.id] || "upcoming"]}
          </li>
        ))}
      </ol>
      <ul className="flow-legend" aria-label="How to read the flow">
        <li>
          <span className="legend-dot is-done" aria-hidden="true" /> done
        </li>
        <li>
          <span className="legend-dot is-active" aria-hidden="true" /> working
        </li>
        <li>
          <Shield size={13} aria-hidden="true" /> human gate (dashed: only if a rule fails)
        </li>
        <li>
          <span className="legend-envelope" aria-hidden="true">inform</span> agent message
        </li>
      </ul>
      {player && <PlayerControls player={player} label={`${title} controls`} valueText={caption} />}
    </figure>
  );
}
