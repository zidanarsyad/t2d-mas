import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  CircleStop,
  MessageSquareText,
  Play,
  Plus,
  ShieldCheck,
} from "lucide-react";
import { request } from "../api";
import {
  Heading,
  Panel,
  SectionTitle,
  Severity,
  Tag,
} from "../components/Primitives";
import OutputSummary from "../components/OutputSummary";
import ReviewControls from "../components/ReviewControls";
import { checkpointLabel, stageInfo, statusLabel, workflow } from "../workflow";
const demo = {
  title: "Checkout service fails during a flash sale",
  body: "During the flash sale, the checkout service reports data corruption for customer orders. The issue affects live order processing and needs investigation before any release. Identify likely causes, propose a scoped fix, and list verification and rollback checks.",
};
export default function TicketTestPage({
  record,
  records,
  onRecord,
  onNavigate,
  onSelectTicket,
  connected,
}) {
  const [title, setTitle] = useState(""),
    [body, setBody] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [inspectedStage, setInspectedStage] = useState(null);
  const autoRun = useRef(false),
    busyRef = useRef(false);
  useEffect(
    () => () => {
      autoRun.current = false;
    },
    [],
  );
  useEffect(() => {
    autoRun.current = false;
    setInspectedStage(null);
    setError("");
    setNotice("");
  }, [record?.ticket_id]);
  const stage =
    inspectedStage ||
    (record?.agent_outputs?.[record.current_stage]
      ? record.current_stage
      : Object.keys(record?.agent_outputs || {}).at(-1)) ||
    record?.current_stage;
  const finish = (next) => {
    if (next.status === "waiting_for_review")
      setNotice(`Paused for review: ${checkpointLabel(next.waiting_for)}.`);
    else if (next.status === "completed")
      setNotice(
        "All nine prototype stages are complete. You can inspect the conversation and decision trail.",
      );
    else if (next.status === "rejected")
      setNotice("The reviewer stopped this run.");
    else setNotice(`Current stage: ${stageInfo(next.current_stage).label}.`);
  };
  async function start(event) {
    event.preventDefault();
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      const next = await request("/sandbox/tickets", "POST", {
        title: title.trim(),
        body: body.trim(),
      });
      onRecord(next);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      busyRef.current = false;
    }
  }
  async function progress(automatic = false) {
    if (!record || busyRef.current) return;
    const id = record.ticket_id;
    busyRef.current = true;
    autoRun.current = automatic;
    setBusy(true);
    setError("");
    setInspectedStage(null);
    try {
      do {
        const next = await request(
          `/sandbox/tickets/${encodeURIComponent(id)}/advance`,
          "POST",
        );
        onRecord(next);
        finish(next);
        if (!automatic || next.status !== "running" || !autoRun.current) break;
        await new Promise((resolve) => setTimeout(resolve, 650));
      } while (autoRun.current);
    } catch (err) {
      setError(err.message);
    } finally {
      autoRun.current = false;
      setBusy(false);
      busyRef.current = false;
    }
  }
  const completed =
    record?.stages?.filter((item) => item.status === "completed").length || 0;
  return (
    <div className="page-wrap">
      <Heading
        eyebrow="Interactive delivery prototype"
        title={record ? "Follow your ticket" : "Let the agents handle an issue"}
        subtitle={
          record
            ? "Inspect each result, follow the handoffs, and decide at human checkpoints."
            : "Describe the problem in everyday language. The agents will assess it and guide it through the workflow."
        }
        action={
          record && (
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => onSelectTicket("")}
            >
              <Plus size={17} />
              New ticket
            </button>
          )
        }
      />
      <div className="workspace-banner subtle">
        <ShieldCheck size={21} />
        <div>
          <b>Safe classroom demonstration</b>
          <p>
            Results are local proposals. Code changes, CI tests, production
            releases, and live monitoring are not connected. Your approval
            advances this prototype.
          </p>
          <details>
            <summary>Data handling & methods</summary>
            <p>
              Common personal information and token patterns are masked before
              storage. If an OpenRouter key is configured, masked ticket text
              and review notes may be sent there. Without a key, triage uses
              local rules. Scores are assessments, not calibrated probabilities.
            </p>
          </details>
        </div>
      </div>
      {!record ? (
        <div className="ticket-entry-layout">
          <Panel className="ticket-entry">
            <SectionTitle
              title="What happened?"
              detail="Include the expected behavior, actual behavior, and who is affected."
            />
            <form onSubmit={start}>
              <label>
                Issue title
                <input
                  required
                  minLength={3}
                  maxLength={180}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="For example: customers cannot complete checkout"
                />
              </label>
              <label>
                Description
                <textarea
                  required
                  minLength={10}
                  maxLength={4000}
                  rows={7}
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  placeholder="Describe the issue, steps to reproduce it, and its business impact…"
                />
                <small>{body.length}/4000 characters</small>
              </label>
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
              <div className="entry-actions">
                <button
                  type="button"
                  className="button secondary"
                  disabled={busy}
                  onClick={() => {
                    setTitle(demo.title);
                    setBody(demo.body);
                  }}
                >
                  Use sample issue
                </button>
                <button
                  className="button primary"
                  disabled={
                    busy || title.trim().length < 3 || body.trim().length < 10
                  }
                >
                  <Play size={17} />
                  {busy ? "Starting…" : "Start ticket"}
                </button>
              </div>
            </form>
          </Panel>
          <Panel className="entry-guide">
            <h2>What happens next?</h2>
            <ol>
              <li>
                <b>Assess the impact</b>
                <span>The triage agent explains the urgency.</span>
              </li>
              <li>
                <b>Watch the teamwork</b>
                <span>Workers bid, then specialist agents share results.</span>
              </li>
              <li>
                <b>Review the decisions</b>
                <span>Accept, request changes, or stop at a checkpoint.</span>
              </li>
            </ol>
            {records.length > 0 && (
              <>
                <SectionTitle title="Continue a ticket" />
                {records.slice(0, 5).map((item) => (
                  <button
                    className="continue-ticket"
                    key={item.ticket_id}
                    onClick={() => onSelectTicket(item.ticket_id)}
                  >
                    <b>{item.title}</b>
                    <small>
                      {statusLabel(item.status)} · {item.ticket_id}
                    </small>
                    <ArrowRight size={16} />
                  </button>
                ))}
              </>
            )}
          </Panel>
        </div>
      ) : (
        <>
          <Panel className="run-summary">
            <div>
              <small className="eyebrow">{record.ticket_id}</small>
              <h2>{record.title}</h2>
              <p>{record.body}</p>
            </div>
            <div>
              <Severity value={record.severity} />
              <Tag
                tone={
                  record.status === "waiting_for_review"
                    ? "amber"
                    : record.status === "completed"
                      ? "green"
                      : "neutral"
                }
              >
                {statusLabel(record.status)}
              </Tag>
            </div>
          </Panel>
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
          <div className="run-toolbar">
            <span>
              <b>{completed} of 9 stages complete</b> ·{" "}
              {stageInfo(record.current_stage).label}
            </span>
            <div>
              {record.status === "running" && (
                <>
                  <button
                    className="button secondary"
                    onClick={() => progress()}
                    disabled={busy}
                  >
                    <ArrowRight size={16} />
                    Next step
                  </button>
                  <button
                    className="button primary"
                    onClick={() => progress(true)}
                    disabled={busy}
                  >
                    <Play size={16} />
                    {busy ? "Working…" : "Run until review"}
                  </button>
                </>
              )}
              {busy && autoRun.current && (
                <button
                  className="button secondary"
                  onClick={() => {
                    autoRun.current = false;
                    setNotice("Stopping after the current step finishes.");
                  }}
                >
                  <CircleStop size={16} />
                  Pause
                </button>
              )}
              <button
                className="button secondary"
                onClick={() => onNavigate("communications", record.ticket_id)}
              >
                <MessageSquareText size={16} />
                See conversation
              </button>
            </div>
          </div>
          <div className="run-layout">
            <Panel className="run-stages">
              <SectionTitle
                title="Nine specialist stages"
                detail="Select a stage to inspect its shared result."
              />
              <ol>
                {workflow.map((item, index) => {
                  const state = record.stages.find(
                    (value) => value.name === item.id,
                  )?.status;
                  return (
                    <li key={item.id}>
                      <button
                        className={`run-stage ${state} ${stage === item.id ? "selected" : ""}`}
                        onClick={() => setInspectedStage(item.id)}
                        aria-pressed={stage === item.id}
                      >
                        <span>
                          {state === "completed" ? (
                            <Check size={15} />
                          ) : (
                            index + 1
                          )}
                        </span>
                        <div>
                          <b>{item.label}</b>
                          <small>{item.agent}</small>
                        </div>
                        <em>
                          {state === "completed"
                            ? "Done"
                            : state === "current"
                              ? record.waiting_for
                                ? "Review"
                                : "Current"
                              : state === "rejected"
                                ? "Stopped"
                                : "Upcoming"}
                        </em>
                      </button>
                    </li>
                  );
                })}
              </ol>
            </Panel>
            <Panel className="run-result">
              <SectionTitle
                title={stageInfo(stage).label}
                detail={`${stageInfo(stage).agent} · shared result`}
              />
              <p className="stage-purpose">{stageInfo(stage).description}</p>
              <OutputSummary output={record.agent_outputs?.[stage]} />
              {record.status === "waiting_for_review" && (
                <div className="checkpoint-callout">
                  <ShieldCheck size={19} />
                  <div>
                    <b>{checkpointLabel(record.waiting_for)}</b>
                    <p>
                      The pipeline is paused. Review the current proposal before
                      deciding.
                    </p>
                  </div>
                </div>
              )}
            </Panel>
          </div>
          {record.status === "waiting_for_review" && (
            <Panel className="run-review">
              <SectionTitle
                title={checkpointLabel(record.waiting_for)}
                detail="Your decision and note are saved with the ticket."
              />
              <ReviewControls
                key={`${record.ticket_id}:${record.waiting_for}`}
                record={record}
                onRecord={(next) => {
                  onRecord(next);
                  setInspectedStage(null);
                  finish(next);
                }}
              />
            </Panel>
          )}
          {record.reviews.length > 0 && (
            <Panel className="run-review-history">
              <SectionTitle
                title="Human decisions"
                detail="Notes and revisions stay attached to this run."
              />
              {record.reviews.map((item, index) => (
                <article key={index}>
                  <Tag
                    tone={
                      item.decision === "accepted"
                        ? "green"
                        : item.decision === "rejected"
                          ? "red"
                          : "amber"
                    }
                  >
                    {item.decision.replaceAll("_", " ")}
                  </Tag>
                  <b>{checkpointLabel(item.checkpoint)}</b>
                  <small>{item.approver}</small>
                  <p>{item.note}</p>
                  {item.interpretation?.summary && (
                    <p className="muted">
                      Agent interpretation: {item.interpretation.summary}
                    </p>
                  )}
                </article>
              ))}
            </Panel>
          )}
          {record.status === "completed" && (
            <div className="workspace-banner">
              <Check size={23} />
              <div>
                <b>Prototype journey completed</b>
                <p>
                  All nine stages and review gates are recorded. Production
                  actions were not executed.
                </p>
              </div>
              <button
                className="button secondary"
                onClick={() => onNavigate("trace", record.ticket_id)}
              >
                Inspect decision trail
                <ArrowRight size={16} />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
