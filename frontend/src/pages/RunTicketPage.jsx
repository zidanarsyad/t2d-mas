import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Check, CircleCheck, CirclePause, CirclePlay, CircleX, Inbox, MessageCircleQuestion, Plus, Route, ShieldAlert, Shuffle, SkipForward, Zap } from "lucide-react";
import { api, isUnavailable } from "../api";
import FeedbackCard from "../components/FeedbackCard";
import GateEvidence from "../components/GateEvidence";
import MobileAgentMap from "../components/MobileAgentMap";
import PipelineFlow from "../components/PipelineFlow";
import ReviewControls from "../components/ReviewControls";
import StageDetails from "../components/StageDetails";
import { EmptyState, Heading, Notice, Panel, SectionTitle, Severity, SourceBadge, StatusBadge, Tag } from "../components/Primitives";
import { mockFeedback } from "../data/mockFeedback.js";
import { sampleConversation, sampleIntro, sampleOutro } from "../data/sampleConversation.js";
import { CHANNELS, channelLabel, languageLabel } from "../lib/feedback.js";
import { replayFrames } from "../lib/flow.js";
import { formatDuration, formatTime, secondsSince } from "../lib/format.js";
import { mobileCostModel, nodeFromMigrationEvent, REPORT_INPUTS, tripFromSnapshot } from "../lib/mobileTrip.js";
import { gateLabel } from "../lib/policy.js";
import { clarificationQuestion, isWaiting, stageEnteredAt, stageInfo, stages, statusLabel } from "../lib/workflow.js";
import { useLiveFlow } from "../hooks/useLiveFlow";
import { useNow } from "../hooks/useNow";
import { useStepPlayer } from "../hooks/useStepPlayer";

export default function RunTicketPage({ workspace, ticketId, onSelectTicket, onNavigate }) {
  const record = workspace.records.find((item) => item.ticket_id === ticketId) || null;
  return record ? (
    <TicketRun workspace={workspace} record={record} onSelectTicket={onSelectTicket} onNavigate={onNavigate} />
  ) : (
    <StartTicket workspace={workspace} onSelectTicket={onSelectTicket} />
  );
}

// ---------------------------------------------------------------------------------------------
// Before a run: pick feedback from the inbox (or type it), then start.

const isFlashSale = (item) => String(item.received_at || "").startsWith("2026-10-10");

function StartTicket({ workspace, onSelectTicket }) {
  const { mode, upsert, records, policy } = workspace;
  const live = mode === "live";
  const [scenario, setScenario] = useState("all");
  const [seed, setSeed] = useState(42);
  const [inbox, setInbox] = useState({ items: [], source: "replay", loading: true });
  const [selected, setSelected] = useState(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [channel, setChannel] = useState("manual");
  const [injectSecret, setInjectSecret] = useState(false);
  const [regression, setRegression] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showReplay, setShowReplay] = useState(false);

  // The live inbox when the backend has it; otherwise the offline sample inbox.
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    let retry;
    setInbox((value) => ({ ...value, loading: true }));
    api
      .feedbackInbox({ seed, count: 10, scenario })
      .then((data) => active && setInbox({ items: data.items || [], source: "live", loading: false }))
      .catch((err) => {
        if (!active) return;
        const items = scenario === "flash_sale" ? mockFeedback.filter(isFlashSale) : mockFeedback;
        setInbox({ items, source: "replay", loading: false, note: isUnavailable(err) ? "" : err.message });
        // The backend is up but the request failed (for example while it was busy):
        // try again a few times instead of staying on the offline sample until a reload.
        if (live && attempt < 3) retry = setTimeout(() => setAttempt((count) => count + 1), 1500);
      });
    return () => {
      active = false;
      clearTimeout(retry);
    };
  }, [scenario, seed, mode, attempt, live]);

  const choose = (item) => {
    setSelected(item);
    setTitle(item.title || "");
    setBody(item.text);
    setChannel(CHANNELS.some((entry) => entry.id === item.channel) ? item.channel : "manual");
    setError("");
  };

  async function start(event) {
    event.preventDefault();
    if (!live || busy) return;
    setBusy(true);
    setError("");
    // An unchanged live inbox message is sent by id, so the backend keeps its metadata.
    const fromInbox = selected && inbox.source === "live" && body.trim() === selected.text.trim();
    const payload = fromInbox ? { feedback_id: selected.feedback_id } : { title: title.trim() || undefined, body: body.trim(), channel };
    try {
      const next = await api.createTicket({ ...payload, inject_test_secret: injectSecret, simulate_regression: regression });
      onSelectTicket(upsert(next).ticket_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <Heading
        eyebrow="Run a ticket"
        title="What happens to one piece of feedback?"
        what="A support inbox of real-style messages in Indonesian and English. Pick one, start it, and watch the agents take it through the pipeline."
        why="You see each agent's reasoning and decide at the human gates yourself."
      />
      {!live && (
        <Notice
          tone="warn"
          icon={ShieldAlert}
          title="Replay mode: the backend is not running"
          action={
            <button type="button" className="button" onClick={() => setShowReplay(true)}>
              <CirclePlay size={15} aria-hidden="true" />
              Watch a recorded run
            </button>
          }
        >
          The inbox below is the offline sample. Starting a real run needs the backend (<code>python -m uvicorn agents.app:app</code>). Meanwhile you can watch the recorded TCK-1042 run.
        </Notice>
      )}
      {showReplay && <RecordedRun policy={policy} onClose={() => setShowReplay(false)} />}

      <div className="split">
        <Panel className="inbox">
          <SectionTitle
            title="Feedback inbox"
            detail="Messages as they arrive from app stores, email, chat, Slack and the crash reporter."
            action={<SourceBadge source={inbox.source} label={inbox.source === "live" ? "Live inbox" : "Offline sample"} />}
          />
          <div className="segmented" role="group" aria-label="Which messages">
            {[
              ["all", "Everything"],
              ["flash_sale", "Flash-sale burst"],
            ].map(([value, label]) => (
              <button key={value} type="button" className={`segment ${scenario === value ? "is-selected" : ""}`} aria-pressed={scenario === value} onClick={() => setScenario(value)}>
                {label}
              </button>
            ))}
          </div>
          {inbox.source === "live" && (
            <button type="button" className="link-button" onClick={() => setSeed((value) => value + 1)}>
              <Shuffle size={14} aria-hidden="true" />
              Show other messages
            </button>
          )}
          {inbox.note && <p className="form-error">{inbox.note}</p>}
          {inbox.loading ? (
            <p className="muted" role="status">
              Loading the inbox…
            </p>
          ) : (
            <ul className="inbox-list">
              {inbox.items.map((item) => (
                <li key={item.feedback_id}>
                  <FeedbackCard item={item} selected={selected?.feedback_id === item.feedback_id} onSelect={choose} />
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel className="start-form">
          <SectionTitle title="Start a ticket" detail={selected ? `From ${channelLabel(selected.channel)} · ${selected.feedback_id}` : "Pick a message, or type your own."} />
          <form onSubmit={start} className="stack">
            <label className="field">
              <span>
                Title <em className="muted">optional: the agent writes one if empty</em>
              </span>
              <input maxLength={180} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="For example: checkout crashes during the flash sale" />
            </label>
            <label className="field">
              <span>What the user wrote</span>
              <textarea required minLength={10} maxLength={4000} rows={6} value={body} onChange={(event) => setBody(event.target.value)} placeholder="Paste or type the feedback, in Indonesian or English…" />
              <small>{body.length}/4000</small>
            </label>
            <label className="field">
              <span>Channel</span>
              <select value={channel} onChange={(event) => setChannel(event.target.value)}>
                {CHANNELS.filter((entry) => entry.id !== "monitoring").map((entry) => (
                  <option key={entry.id} value={entry.id}>
                    {entry.label}
                  </option>
                ))}
              </select>
            </label>
            <fieldset className="options">
              <legend>Demo options</legend>
              <label className="check">
                <input type="checkbox" checked={injectSecret} onChange={(event) => setInjectSecret(event.target.checked)} />
                Put a test secret in the draft change (the secret scan must stop it)
              </label>
              <label className="check">
                <input type="checkbox" checked={regression} onChange={(event) => setRegression(event.target.checked)} />
                Ship a regression (monitoring must open a follow-up ticket)
              </label>
            </fieldset>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <div className="button-row">
              <button type="submit" className="button button-primary" disabled={!live || busy || body.trim().length < 10}>
                <CirclePlay size={16} aria-hidden="true" />
                {busy ? "Starting…" : "Start this ticket"}
              </button>
            </div>
            {!live && <p className="muted small">Starting is disabled in replay mode.</p>}
          </form>
          {records.length > 0 && (
            <>
              <SectionTitle title="Or continue a ticket" level={3} />
              <ul className="plain-list continue-list">
                {records.slice(0, 5).map((item) => (
                  <li key={item.ticket_id}>
                    <button type="button" className="continue-ticket" onClick={() => onSelectTicket(item.ticket_id)}>
                      <span>
                        <b>{item.title}</b>
                        <small>
                          {item.ticket_id} · {statusLabel(item.status)}
                        </small>
                      </span>
                      <ArrowRight size={16} aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Panel>
      </div>
    </div>
  );
}

/** The recorded TCK-1042 run, for replay mode. */
function RecordedRun({ policy, onClose }) {
  const frames = useMemo(() => replayFrames(sampleConversation, { intro: sampleIntro, outro: sampleOutro, policy }), [policy]);
  const player = useStepPlayer(frames, { autoPlay: true });
  const stage = player.step?.marker?.stage || "intake";
  return (
    <Panel className="recorded-run">
      <SectionTitle
        title="Recorded run: TCK-1042"
        detail="Illustrative replay of the report's flash-sale story. It is not your ticket."
        action={
          <button type="button" className="button button-small" onClick={onClose}>
            Close
          </button>
        }
      />
      <PipelineFlow frame={player.step} player={player} source="replay" title="Recorded TCK-1042 run" ticketLabel="TCK-1042" policy={policy} />
      <StageDetails record={null} stageId={stage} policy={policy} />
    </Panel>
  );
}

// ---------------------------------------------------------------------------------------------
// During a run: the animated journey, each stage's result, and the review at a gate.

function TicketRun({ workspace, record, onSelectTicket, onNavigate }) {
  const { messages, policy, upsert, subscribe, mode } = workspace;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [inspected, setInspected] = useState(null);
  const [visits, setVisits] = useState([]);
  const autoRun = useRef(false);
  const busyRef = useRef(false);
  const now = useNow(15000);
  const { frame } = useLiveFlow(record, messages, policy);
  const model = useMemo(() => mobileCostModel(REPORT_INPUTS, policy), [policy]);

  useEffect(() => {
    autoRun.current = false;
    setInspected(null);
    setError("");
    setNotice("");
    setVisits([]);
  }, [record.ticket_id]);

  // Scout-Log reports each node as it answers; show those before the stage result arrives.
  useEffect(
    () =>
      subscribe((event) => {
        if (event?.type === "agent.migrated" && event.ticket_id === record.ticket_id) {
          setVisits((items) => [...items.filter((item) => item.node_id !== event.node_id), nodeFromMigrationEvent(event)]);
        }
      }),
    [subscribe, record.ticket_id],
  );

  const outputs = record.agent_outputs;
  const stage = inspected || (outputs[record.current_stage] ? record.current_stage : Object.keys(outputs).at(-1)) || record.current_stage;
  const trip = tripFromSnapshot(record) || (visits.length ? { source: "live", nodes: visits } : null);
  const waiting = isWaiting(record);
  const completed = record.stages.filter((item) => item.status === "completed").length;

  /** One line on what just happened; `intent` is set when it followed a review decision. */
  const describe = (next, intent) => {
    if (clarificationQuestion(next)) setNotice("The agent could not act on that note. Its question is shown above the review form.");
    else if (next.status === "waiting_for_review") setNotice(`Paused for a human: ${gateLabel(next.pending_gate?.gate || next.waiting_for, policy)}.`);
    else if (next.status === "completed") setNotice("All nine stages ran. Open the Decision trace to see why each step happened.");
    else if (next.status === "rejected") setNotice("The reviewer stopped this run. The reason is in the audit log.");
    else if (next.status === "duplicate") setNotice(`Linked as a duplicate of ${next.duplicate_of}. This run is closed.`);
    else if (intent === "request_changes") setNotice(`The agent revised its ${stageInfo(next.current_stage).name.toLowerCase()} result. Check it, then continue the run.`);
    else if (intent === "accept") setNotice(`Approved and recorded. Next: ${stageInfo(next.current_stage).name}.`);
    else setNotice(`Next: ${stageInfo(next.current_stage).name}.`);
  };

  async function progress(automatic = false) {
    if (busyRef.current) return;
    busyRef.current = true;
    autoRun.current = automatic;
    setBusy(true);
    setError("");
    setInspected(null);
    try {
      do {
        const next = upsert(await api.advance(record.ticket_id));
        describe(next);
        if (!automatic || next.status !== "running" || !autoRun.current) break;
        await new Promise((resolve) => window.setTimeout(resolve, 650));
      } while (autoRun.current);
    } catch (err) {
      setError(err.message);
    } finally {
      autoRun.current = false;
      busyRef.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <Heading
        eyebrow={`Run a ticket · ${record.ticket_id}`}
        title={record.title}
        what="The ticket's journey through the nine agents, animated as their messages arrive."
        why="Select a stage to see what its agent perceived, remembered, reasoned, did and reported."
        action={
          <button type="button" className="button" disabled={busy} onClick={() => onSelectTicket("")}>
            <Plus size={16} aria-hidden="true" />
            New ticket
          </button>
        }
      />
      {mode !== "live" && (
        <Notice tone="warn" icon={ShieldAlert} title="The backend is not reachable">
          This ticket cannot move until the backend is back. What you see is its last saved state.
        </Notice>
      )}

      <Panel className="ticket-summary">
        <div className="ticket-summary-main">
          <p className="ticket-body" lang={record.language === "en" ? "en" : "id"}>
            {record.body}
          </p>
          <ul className="chip-list" aria-label="Ticket facts">
            <li>
              <Severity value={record.severity} />
            </li>
            <li>
              <StatusBadge status={record.status} />
            </li>
            <li>
              <Tag icon={Inbox}>{channelLabel(record.channel)}</Tag>
            </li>
            {record.language && (
              <li>
                <Tag>{languageLabel(record.language)}</Tag>
              </li>
            )}
            {record.component && (
              <li>
                <Tag>Component: {record.component}</Tag>
              </li>
            )}
            {record.sla_due && (
              <li>
                <Tag>SLA due {formatTime(record.sla_due, { date: true, seconds: false })}</Tag>
              </li>
            )}
          </ul>
        </div>
        {(record.duplicate_of || record.parent_ticket_id) && (
          <p className="muted">
            {record.duplicate_of && (
              <>
                Duplicate of{" "}
                <button type="button" className="link-button" onClick={() => onSelectTicket(record.duplicate_of)}>
                  {record.duplicate_of}
                </button>
                .{" "}
              </>
            )}
            {record.parent_ticket_id && (
              <>
                Follow-up of{" "}
                <button type="button" className="link-button" onClick={() => onSelectTicket(record.parent_ticket_id)}>
                  {record.parent_ticket_id}
                </button>
                .
              </>
            )}
          </p>
        )}
      </Panel>

      <div className="run-toolbar">
        <span>
          <b>
            {completed} of {stages.length} stages done
          </b>{" "}
          · now at {stageInfo(record.current_stage).name}
        </span>
        <div className="button-row">
          {record.status === "running" && (
            <>
              <button type="button" className="button" onClick={() => progress(false)} disabled={busy || mode !== "live"}>
                <SkipForward size={16} aria-hidden="true" />
                Next step
              </button>
              <button type="button" className="button button-primary" onClick={() => progress(true)} disabled={busy || mode !== "live"}>
                <CirclePlay size={16} aria-hidden="true" />
                {busy ? "Working…" : "Run until a human is needed"}
              </button>
            </>
          )}
          {busy && autoRun.current && (
            <button
              type="button"
              className="button"
              onClick={() => {
                autoRun.current = false;
                setNotice("Pausing after the current step.");
              }}
            >
              <CirclePause size={16} aria-hidden="true" />
              Pause
            </button>
          )}
          <button type="button" className="button" onClick={() => onNavigate("trace", record.ticket_id)}>
            <Route size={16} aria-hidden="true" />
            Decision trace
          </button>
        </div>
      </div>
      {notice && (
        <p className="form-notice" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      <Panel>
        <PipelineFlow frame={frame} source="live" title={`${record.ticket_id} live journey`} ticketLabel={record.ticket_id} selectedStage={stage} onSelectStage={setInspected} policy={policy} />
      </Panel>

      {waiting && (
        <Panel className="review-panel">
          <SectionTitle title={`Waiting for a human: ${gateLabel(record.pending_gate?.gate, policy)}`} detail="Your decision and reason are written to the append-only audit log." />
          <GateEvidence record={record} policy={policy} />
          <ReviewControls
            key={`${record.ticket_id}:${record.pending_gate?.gate}:${record.reviews.length}`}
            record={record}
            onRecord={(next, intent) => {
              const saved = upsert(next);
              setInspected(null);
              describe(saved, intent);
              return saved;
            }}
          />
        </Panel>
      )}

      <div className="run-layout">
        <Panel>
          <SectionTitle title="Stages" detail="Select one to inspect it." level={3} />
          <ol className="stage-list">
            {stages.map((item, index) => {
              const entry = record.stages.find((value) => value.name === item.id);
              const state = entry?.status || "upcoming";
              const entered = stageEnteredAt(record, item.id);
              const current = item.id === record.current_stage && !["completed", "duplicate"].includes(record.status);
              const Icon = state === "completed" ? CircleCheck : state === "rejected" ? CircleX : null;
              return (
                <li key={item.id}>
                  <button type="button" className={`stage-button state-${state} ${stage === item.id ? "is-selected" : ""}`} aria-pressed={stage === item.id} onClick={() => setInspected(item.id)}>
                    <span className="stage-number" aria-hidden="true">
                      {Icon ? <Icon size={15} /> : index + 1}
                    </span>
                    <span className="stage-text">
                      <b>{item.name}</b>
                      <small>{entry?.agent || item.agent}</small>
                    </span>
                    <em>
                      {state === "completed"
                        ? "Done"
                        : state === "rejected"
                          ? "Stopped"
                          : state === "skipped"
                            ? "Skipped"
                            : current
                              ? waiting
                                ? "Waiting for a human"
                                : `${outputs[item.id] ? "Result ready" : "Up next"}${entered ? ` · here for ${formatDuration(secondsSince(entered, now))}` : ""}`
                              : "Upcoming"}
                    </em>
                  </button>
                </li>
              );
            })}
          </ol>
        </Panel>
        <Panel className="stage-panel">
          <StageDetails record={record} stageId={stage} policy={policy} />
          {stage === "investigation" && trip && <MobileAgentMap trip={trip} model={model} source="live" title="Scout-Log trip for this ticket" compact />}
        </Panel>
      </div>

      {(record.reviews.length > 0 || record.irreversible_actions.length > 0 || record.follow_up_ticket_ids.length > 0) && (
        <Panel>
          <SectionTitle title="Human decisions and actions" detail="Everything here is also in the audit log." />
          <ul className="decision-history">
            {record.reviews.map((item, index) => (
              <li key={`review-${index}`} className={`decision-${item.decision}`}>
                {item.decision === "accepted" ? <Check size={15} aria-hidden="true" /> : item.decision === "rejected" ? <CircleX size={15} aria-hidden="true" /> : <ShieldAlert size={15} aria-hidden="true" />}
                <span>
                  <b>
                    {String(item.decision).replaceAll("_", " ")} · {gateLabel(item.checkpoint, policy)}
                  </b>{" "}
                  by {item.approver}
                  {item.at && <> at {formatTime(item.at)}</>}
                  <span className="muted"> “{item.note}”</span>
                  {item.decision === "clarification_requested" && item.interpretation?.clarification_question ? (
                    <small className="clarification">
                      <MessageCircleQuestion size={13} aria-hidden="true" /> The agent asked: {item.interpretation.clarification_question}
                    </small>
                  ) : (
                    item.interpretation?.summary && <small>Agent's reading of the note: {item.interpretation.summary}</small>
                  )}
                </span>
              </li>
            ))}
            {record.irreversible_actions.map((item, index) => (
              <li key={`action-${index}`} className={item.executed ? "decision-accepted" : "decision-rejected"}>
                <Zap size={15} aria-hidden="true" />
                <span>
                  <b>
                    {item.action === "full_deploy" ? "Full deploy" : item.action === "merge" ? "Merge" : item.action}: {item.executed ? "executed" : "blocked"}
                  </b>{" "}
                  {item.human_approved ? `with ${item.approver}'s recorded approval` : "— no recorded approval"}
                </span>
              </li>
            ))}
            {record.follow_up_ticket_ids.map((id) => (
              <li key={id}>
                <ArrowRight size={15} aria-hidden="true" />
                <span>
                  Monitoring opened a follow-up ticket:{" "}
                  <button type="button" className="link-button" onClick={() => onSelectTicket(id)}>
                    {id}
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {record.status === "completed" && (
        <Notice tone="ok" icon={CircleCheck} title="Prototype run finished" action={<button type="button" className="button" onClick={() => onNavigate("trace", record.ticket_id)}>Open the decision trace</button>}>
          All nine stages ran and every gate decision is recorded. Real production systems were not touched.
        </Notice>
      )}
      {!Object.keys(outputs).length && <EmptyState title="Nothing has run yet">Press Next step to send the ticket to Triage.</EmptyState>}
    </div>
  );
}
