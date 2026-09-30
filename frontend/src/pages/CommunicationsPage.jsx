import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  Bot,
  Check,
  MessageSquareText,
  Pause,
  Play,
  Plus,
  RotateCcw,
  ShieldCheck,
  Users,
} from "lucide-react";
import { Heading, Panel, SectionTitle, Tag } from "../components/Primitives";
import OutputSummary from "../components/OutputSummary";
import { sampleConversation } from "../sampleConversation";
import {
  localTime,
  messageLabel,
  messageMeaning,
  recipients,
  stageInfo,
  workflow,
} from "../workflow";

export default function CommunicationsPage({
  messages = [],
  records = [],
  ticketId,
  onSelectTicket,
  connected,
  onNavigate,
}) {
  const [source, setSource] = useState(ticketId || "sample");
  const handoffRef = useRef(null);
  const [selection, setSelection] = useState(null),
    [playing, setPlaying] = useState(false);
  const sample = source === "sample";
  const ids = [
    ...new Set([
      ...records.map((item) => item.ticket_id),
      ...messages.map((item) => item.correlation_id),
    ]),
  ];
  const conversation = useMemo(
    () =>
      sample
        ? sampleConversation
        : messages.filter((item) => item.correlation_id === source),
    [sample, messages, source],
  );
  const selected =
    conversation.find((item) => item.message_id === selection) ||
    (sample ? conversation[8] : conversation.at(-1));
  const index = Math.max(0, conversation.indexOf(selected));
  const ticket = records.find((item) => item.ticket_id === source);
  useEffect(() => {
    setSource(ticketId || "sample");
    setSelection(null);
    setPlaying(false);
  }, [ticketId]);
  useEffect(() => {
    if (!playing || !sample) return;
    const timer = window.setInterval(
      () =>
        setSelection((current) => {
          const next =
            sampleConversation.findIndex(
              (item) => item.message_id === current,
            ) + 1;
          if (next >= sampleConversation.length) {
            setPlaying(false);
            return current;
          }
          return sampleConversation[next].message_id;
        }),
      1800,
    );
    return () => window.clearInterval(timer);
  }, [playing, sample]);
  const chooseSource = (next) => {
    setSource(next);
    onSelectTicket(next === "sample" ? "" : next);
    setSelection(null);
    setPlaying(false);
  };
  const bids = conversation
    .slice(0, index + 1)
    .filter((item) => item.performative === "propose")
    .map((item) => item.content);
  const award = conversation
    .slice(0, index + 1)
    .findLast((item) => item.performative === "accept-proposal")?.content;
  const output = selected?.content?.output;
  const participants = new Set(
    conversation.flatMap((item) => [item.sender, ...recipients(item)]),
  );
  return (
    <div className="page-wrap conversation-page">
      <Heading
        eyebrow="See the teamwork"
        title="How do the agents work together?"
        subtitle="Follow a ticket’s conversation: who asks, who responds, what is decided, and what happens next."
        action={
          <button
            className="button primary"
            onClick={() => onNavigate("test", "")}
          >
            <Plus size={17} />
            Run a ticket
          </button>
        }
      />
      <div className="conversation-toolbar">
        <label>
          Conversation
          <select
            aria-label="Choose a conversation"
            value={source}
            onChange={(event) => chooseSource(event.target.value)}
          >
            <option value="sample">Example · Flash sale checkout</option>
            {ids.map((id) => (
              <option key={id} value={id}>
                {id} ·{" "}
                {records.find((item) => item.ticket_id === id)?.title ||
                  "Recorded conversation"}
              </option>
            ))}
          </select>
        </label>
        <Tag tone={sample ? "purple" : "green"}>
          {sample ? "Illustrative walkthrough" : "Recorded agent messages"}
        </Tag>
        {sample ? (
          <div className="replay-controls">
            <button
              className="button secondary"
              onClick={() => {
                if (!playing) setSelection(sampleConversation[0].message_id);
                setPlaying(!playing);
              }}
            >
              {playing ? <Pause size={16} /> : <Play size={16} />}{" "}
              {playing ? "Pause" : "Play walkthrough"}
            </button>
            <button
              className="icon-btn"
              aria-label="Restart walkthrough"
              onClick={() => {
                setSelection(sampleConversation[0].message_id);
                setPlaying(false);
              }}
            >
              <RotateCcw size={17} />
            </button>
          </div>
        ) : (
          <span className="muted">
            {connected
              ? "New messages arrive automatically"
              : "Showing recovered messages · backend offline"}
          </span>
        )}
      </div>
      <div className="workspace-banner subtle">
        <MessageSquareText size={22} />
        <div>
          <b>
            {sample
              ? "A complete example, from issue intake to the feedback loop"
              : ticket?.title || source}
          </b>
          <p>
            {sample
              ? "This walkthrough uses the report’s worker bidding example. Start a ticket to see messages produced by the prototype."
              : "Every message below belongs to this ticket. Selection stays in place as new messages arrive."}
          </p>
        </div>
        <span className="conversation-count">
          {conversation.length} messages · {participants.size} participants
        </span>
      </div>
      <div className="workflow-strip" aria-label="Nine delivery stages">
        {workflow.map((stage, i) => (
          <div
            className={selected?.content?.stage === stage.id ? "current" : ""}
            key={stage.id}
          >
            <span>{i + 1}</span>
            <b>{stage.label}</b>
          </div>
        ))}
      </div>
      {!conversation.length ? (
        <Panel className="empty-state">
          <MessageSquareText size={32} />
          <h2>No messages for this ticket yet</h2>
          <p>
            Run a ticket to see its handoffs, worker bids, policy decisions, and
            human feedback here.
          </p>
          <button
            className="button primary"
            onClick={() => onNavigate("test", ticketId)}
          >
            Open ticket workspace
            <ArrowRight size={16} />
          </button>
        </Panel>
      ) : (
        <>
          <div className="conversation-layout" ref={handoffRef}>
            <Panel className="conversation-focus">
              <div className="focus-heading">
                <SectionTitle
                  title="The selected handoff"
                  detail={`Message ${index + 1} of ${conversation.length} · ${localTime(selected.occurred_at)} WIB`}
                />
                <Tag
                  tone={
                    selected.performative === "accept-proposal"
                      ? "green"
                      : "purple"
                  }
                >
                  {messageLabel(selected.performative)}
                </Tag>
              </div>
              <div className="handoff-route">
                <div className="participant sender">
                  <span>
                    <Bot size={23} />
                  </span>
                  <small>SENDS</small>
                  <b>{selected.sender}</b>
                </div>
                <div className="handoff-arrow">
                  <ArrowRight size={30} />
                  <small>
                    {selected.performative === "propose"
                      ? "Worker bid"
                      : selected.content?.decision
                        ? "Decision"
                        : "Shared result"}
                  </small>
                </div>
                <div className="recipient-stack">
                  {recipients(selected).map((receiver) => (
                    <div className="participant" key={receiver}>
                      <span>
                        {receiver === "Human-Reviewer" ? (
                          <Users size={23} />
                        ) : (
                          <Bot size={23} />
                        )}
                      </span>
                      <small>RECEIVES</small>
                      <b>{receiver}</b>
                    </div>
                  ))}
                </div>
              </div>
              <div className="handoff-explanation">
                <small>WHAT THIS MEANS</small>
                <h2>{messageLabel(selected.performative)}</h2>
                <p>{messageMeaning(selected)}</p>
              </div>
              {selected.content?.note && (
                <blockquote className="reviewer-quote">
                  <ShieldCheck size={17} />
                  <span>{selected.content.note}</span>
                </blockquote>
              )}
              {output && (
                <div className="shared-result">
                  <SectionTitle
                    title="What the agent shared"
                    detail={
                      selected.content.stage
                        ? stageInfo(selected.content.stage).label
                        : undefined
                    }
                  />
                  <OutputSummary output={output} />
                </div>
              )}
              {bids.length > 0 &&
                [
                  "cfp",
                  "propose",
                  "accept-proposal",
                  "reject-proposal",
                ].includes(selected.performative) && (
                  <div className="bid-comparison">
                    <SectionTitle
                      title="How the worker is selected"
                      detail="50% skill + 30% available capacity + 20% cost efficiency. A higher score wins."
                    />
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Worker</th>
                            <th>Skill</th>
                            <th>Workload</th>
                            <th>Cost index</th>
                            <th>Score</th>
                          </tr>
                        </thead>
                        <tbody>
                          {bids.map((bid) => (
                            <tr
                              className={
                                award?.worker_id === bid.worker_id
                                  ? "bid-winner"
                                  : ""
                              }
                              key={bid.worker_id}
                            >
                              <td>
                                {award?.worker_id === bid.worker_id && (
                                  <Check size={14} />
                                )}{" "}
                                {bid.worker_id}
                              </td>
                              <td>{Math.round(bid.skill * 100)}%</td>
                              <td>{Math.round(bid.load * 100)}%</td>
                              <td>{Number(bid.cost).toFixed(2)}</td>
                              <td>
                                <b>{Number(bid.utility).toFixed(3)}</b>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="bid-note">
                      A lower workload means more available time. Cost is a
                      normalized index; a lower value is cheaper.
                    </p>
                    {award && (
                      <p className="bid-note">
                        {award.worker_id} offers the strongest balance of skill,
                        available time, and cost.
                      </p>
                    )}
                  </div>
                )}
              <details className="technical-details">
                <summary>Protocol details · {selected.performative}</summary>
                <dl>
                  <div>
                    <dt>Ticket reference / correlation ID</dt>
                    <dd>{selected.correlation_id}</dd>
                  </div>
                  <div>
                    <dt>Message ID</dt>
                    <dd>{selected.message_id}</dd>
                  </div>
                </dl>
                <pre>
                  {JSON.stringify(
                    {
                      content: selected.content,
                      policy_context: selected.policy_context,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
            </Panel>
            <Panel className="conversation-timeline">
              <div className="focus-heading">
                <SectionTitle
                  title="The conversation"
                  detail="Select any message to understand the exchange."
                />
              </div>
              <ol>
                {conversation.map((message, i) => (
                  <li key={message.message_id}>
                    <button
                      className={
                        selected.message_id === message.message_id
                          ? "selected"
                          : ""
                      }
                      aria-pressed={selected.message_id === message.message_id}
                      onClick={() => {
                        setSelection(message.message_id);
                        setPlaying(false);
                        if (window.matchMedia("(max-width: 950px)").matches) {
                          handoffRef.current?.scrollIntoView({
                            block: "start",
                            behavior: window.matchMedia(
                              "(prefers-reduced-motion: reduce)",
                            ).matches
                              ? "auto"
                              : "smooth",
                          });
                        }
                      }}
                    >
                      <span
                        className={`conversation-event-icon ${message.performative === "accept-proposal" ? "award" : ""}`}
                      >
                        {message.performative === "accept-proposal" ? (
                          <Check size={15} />
                        ) : message.content?.decision ? (
                          <ShieldCheck size={15} />
                        ) : (
                          <MessageSquareText size={15} />
                        )}
                      </span>
                      <span className="conversation-event">
                        <span>
                          <b>{messageLabel(message.performative)}</b>
                          <time>{localTime(message.occurred_at)}</time>
                        </span>
                        <strong>
                          {message.sender}
                          <ArrowRight size={12} />
                          {recipients(message).join(", ")}
                        </strong>
                        <small>
                          {message.content?.stage
                            ? stageInfo(message.content.stage).label
                            : message.content?.checkpoint
                              ? "Human checkpoint"
                              : message.performative === "propose"
                                ? `Selection score ${Number(message.content.utility).toFixed(3)}`
                                : "Coordination & decision"}
                        </small>
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            </Panel>
          </div>
          <div className="communication-principles">
            <span>
              <MessageSquareText size={17} />
              <b>Shared ticket reference</b> keeps every exchange connected
            </span>
            <span>
              <ShieldCheck size={17} />
              <b>Human checkpoints</b> keep risky decisions reviewable
            </span>
            <span>
              <ArrowDown size={17} />
              <b>Monitoring → triage</b> completes the feedback loop
            </span>
          </div>
        </>
      )}
    </div>
  );
}
