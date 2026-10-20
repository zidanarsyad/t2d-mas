import { useEffect, useMemo, useState } from "react";
import { Download, ShieldCheck } from "lucide-react";
import { api } from "../api";
import BidTable from "../components/BidTable";
import ExportDialog from "../components/ExportDialog";
import OutputSummary from "../components/OutputSummary";
import PipelineFlow from "../components/PipelineFlow";
import Term from "../components/Term";
import TraceTimeline from "../components/TraceTimeline";
import { EmptyState, Heading, Notice, Panel, SectionTitle, SourceBadge } from "../components/Primitives";
import { sampleConversation, sampleIntro, sampleOutro } from "../data/sampleConversation.js";
import { framesFromMessages, replayFrames } from "../lib/flow.js";
import { formatNumber, formatTime } from "../lib/format.js";
import { policySourceLabel } from "../lib/policy.js";
import { entriesFromAudit, entriesFromMessages } from "../lib/trace.js";
import { performativeLabel, recipients, shortAgentName } from "../lib/workflow.js";
import { useStepPlayer } from "../hooks/useStepPlayer";

const SAMPLE = "";

export default function TracePage({ workspace, ticketId, onSelectTicket }) {
  const { records, messages, policy } = workspace;
  const source = records.some((item) => item.ticket_id === ticketId) || messages.some((item) => item.correlation_id === ticketId) ? ticketId : SAMPLE;
  const sample = source === SAMPLE;
  const ticket = records.find((item) => item.ticket_id === source);
  const [audit, setAudit] = useState(null);
  const [exportData, setExportData] = useState(null);

  const conversation = useMemo(() => (sample ? sampleConversation : messages.filter((item) => item.correlation_id === source)), [sample, messages, source]);

  // A reloaded page may have lost the live messages; the saved audit log still has the story.
  useEffect(() => {
    setAudit(null);
    if (sample || conversation.length) return undefined;
    let active = true;
    api
      .ticketHistory(50)
      .then((items) => active && setAudit(items.find((item) => item.ticket_id === source)?.events || []))
      .catch(() => active && setAudit([]));
    return () => {
      active = false;
    };
  }, [sample, source, conversation.length]);

  const frames = useMemo(
    () => (sample ? replayFrames(sampleConversation, { intro: sampleIntro, outro: sampleOutro, policy }) : framesFromMessages(conversation, { policy, prefix: `trace-${source}` })),
    [sample, conversation, source, policy],
  );
  const entries = useMemo(() => (conversation.length ? entriesFromMessages(conversation, policy) : entriesFromAudit(audit || [], policy)), [conversation, audit, policy]);
  const player = useStepPlayer(frames, { autoPlay: false });
  // The sample replay has an intro frame before the first message.
  const offset = sample ? 1 : 0;
  const selectedEntry = conversation.length ? Math.min(Math.max(player.index - offset, 0), entries.length - 1) : -1;
  const message = conversation[selectedEntry];
  const bids = conversation.slice(0, selectedEntry + 1).filter((item) => item.performative === "propose").map((item) => item.content);
  const winner = conversation.slice(0, selectedEntry + 1).findLast((item) => item.performative === "accept-proposal")?.content?.worker_id;
  const options = [...new Set([...records.map((item) => item.ticket_id), ...messages.map((item) => item.correlation_id).filter(Boolean)])];
  const recordTitle = (id) => records.find((item) => item.ticket_id === id)?.title;

  function exportTrace() {
    setExportData({
      content: JSON.stringify({ source: sample ? "illustrative_example" : "recorded_messages", ticket: ticket || null, messages: conversation, audit_events: conversation.length ? undefined : audit }, null, 2),
      type: "application/json",
      filename: `t2d-${source || "TCK-1042-example"}-trace.json`,
      description: `${entries.length} ${sample ? "illustrative" : "recorded"} steps for ${source || "the TCK-1042 example"}. Only this trace is exported.`,
    });
  }

  return (
    <div className="page">
      {exportData && <ExportDialog {...exportData} onClose={() => setExportData(null)} />}
      <Heading
        eyebrow="Decision trace"
        title="Why was this decided?"
        what="One ticket's messages, policy checks and human decisions in order. Pick a row to jump the animation to that moment."
        why="Every automatic decision can be explained, and every human decision has a recorded reason."
        action={
          <button type="button" className="button" onClick={exportTrace} disabled={!entries.length}>
            <Download size={16} aria-hidden="true" />
            Export JSON
          </button>
        }
      />
      <div className="toolbar">
        <label className="field field-inline">
          <span>Ticket</span>
          <select value={source} onChange={(event) => onSelectTicket(event.target.value)}>
            <option value={SAMPLE}>Example · TCK-1042 flash sale (replay)</option>
            {options.map((id) => (
              <option key={id} value={id}>
                {id}
                {recordTitle(id) ? ` · ${recordTitle(id)}` : ""}
              </option>
            ))}
          </select>
        </label>
        <SourceBadge source={sample ? "replay" : conversation.length ? "live" : "recorded"} />
      </div>

      {!sample && !conversation.length && audit === null && (
        <p className="muted" role="status">
          Loading the saved audit log…
        </p>
      )}
      {!sample && !conversation.length && audit && !audit.length && <Notice title="No messages recorded for this ticket yet">Run it from Run a ticket, then come back.</Notice>}

      {frames.length > 0 && (
        <Panel>
          <PipelineFlow frame={player.step} player={player} source={sample ? "replay" : "recorded"} title={sample ? "TCK-1042 decision trace" : `${source} decision trace`} ticketLabel={source || "TCK-1042"} policy={policy} />
        </Panel>
      )}

      <div className="split split-trace">
        <Panel className="list-panel">
          <SectionTitle title="Timeline" detail={`${entries.length} steps · times in WIB`} level={3} />
          {entries.length ? (
            <TraceTimeline entries={entries} selectedIndex={selectedEntry} onSelect={conversation.length ? (index) => player.seek(index + offset) : undefined} />
          ) : (
            <EmptyState title="Nothing to show yet" />
          )}
        </Panel>
        <div className="stack">
          {message && (
            <Panel className="detail-panel">
              <p className="eyebrow">
                Step {selectedEntry + 1} · {formatTime(message.occurred_at)}
              </p>
              <h2>
                {entries[selectedEntry]?.title || performativeLabel(message.performative)} <code className="raw-name">{message.performative}</code>
              </h2>
              <p>
                <b>{shortAgentName(message.sender)}</b> → {recipients(message).map(shortAgentName).join(", ")}
              </p>
              <p>{entries[selectedEntry]?.detail}</p>
              {message.content?.note && <blockquote className="original-text">“{message.content.note}”</blockquote>}
              {bids.length > 0 && message.content?.stage === "assignment" && <BidTable bids={bids} winner={winner} />}
              {message.content?.output && <OutputSummary output={message.content.output} />}
              {message.policy_context && Object.keys(message.policy_context).length > 0 && (
                <p className="muted small">
                  Policy attached to this message: <Term id="tau">τ</Term> {formatNumber(message.policy_context.tau, 2)} · <Term id="risk-max">R_max</Term> {formatNumber(message.policy_context.risk_max, 2)}
                </p>
              )}
            </Panel>
          )}
          <Panel className="policy-panel">
            <ShieldCheck size={22} aria-hidden="true" />
            <h2>When does a person decide?</h2>
            <dl className="facts">
              <div>
                <dt>
                  <Term id="tau">Minimum confidence (τ)</Term>
                </dt>
                <dd>{formatNumber(policy.tau, 2)}</dd>
              </div>
              <div>
                <dt>
                  <Term id="risk-max">Maximum risk (R_max)</Term>
                </dt>
                <dd>{formatNumber(policy.risk_max, 2)}</dd>
              </div>
              <div>
                <dt>Risk by severity</dt>
                <dd>
                  {Object.entries(policy.risk_by_class)
                    .map(([name, value]) => `${name} ${formatNumber(value, 2)}`)
                    .join(" · ")}
                </dd>
              </div>
              <div>
                <dt>
                  <Term id="duplicate-bands">Duplicate bands</Term>
                </dt>
                <dd>
                  link ≥ {formatNumber(policy.duplicate.auto_link, 2)} · ask ≥ {formatNumber(policy.duplicate.review, 2)}
                </dd>
              </div>
              <div>
                <dt>
                  <Term id="canary">Canary starts alone</Term>
                </dt>
                <dd>risk ≤ {formatNumber(policy.canary.risk_max, 2)}</dd>
              </div>
            </dl>
            <p className="muted small">
              An agent acts alone only when confidence ≥ τ <b>and</b> risk ≤ R_max. Merges and full releases always need a person. {policySourceLabel(policy)}.
            </p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
