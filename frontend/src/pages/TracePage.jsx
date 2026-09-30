import { useState } from "react";
import { Download, MessageSquareText, ShieldCheck } from "lucide-react";
import { Heading, Panel, SectionTitle, Tag } from "../components/Primitives";
import OutputSummary from "../components/OutputSummary";
import ExportDialog from "../components/ExportDialog";
import { sampleConversation } from "../sampleConversation";
import {
  localTime,
  messageLabel,
  messageMeaning,
  recipients,
  stageInfo,
} from "../workflow";
export default function TracePage({
  records = [],
  messages = [],
  ticketId,
  onSelectTicket,
  onNavigate,
}) {
  const [open, setOpen] = useState(null);
  const [exportData, setExportData] = useState(null);
  const sample = !ticketId;
  const ids = [
    ...new Set([
      ...records.map((item) => item.ticket_id),
      ...messages.map((item) => item.correlation_id),
    ]),
  ];
  const events = sample
    ? sampleConversation
    : messages.filter((item) => item.correlation_id === ticketId);
  const ticket = records.find((item) => item.ticket_id === ticketId);
  function exportTrace() {
    setExportData({
      content: JSON.stringify(
        {
          source: sample ? "illustrative_example" : "recorded_messages",
          ticket: ticket || null,
          messages: events,
        },
        null,
        2,
      ),
      type: "application/json",
      filename: `t2d-${ticketId || "example"}-trace.json`,
      description: `${events.length} ${sample ? "illustrative" : "recorded"} messages for ${ticketId || "the flash sale example"}. This export contains only the selected trail.`,
    });
  }
  return (
    <div className="page-wrap">
      {exportData && (
        <ExportDialog {...exportData} onClose={() => setExportData(null)} />
      )}
      <Heading
        eyebrow="Evidence & accountability"
        title="Why was that decision made?"
        subtitle="Follow the inputs, shared results, policy checks, and human feedback for one ticket."
        action={
          <button
            className="button secondary"
            disabled={!events.length}
            onClick={exportTrace}
          >
            <Download size={17} />
            Export this trail
          </button>
        }
      />
      <div className="conversation-toolbar">
        <label>
          Ticket
          <select
            aria-label="Choose decision trail ticket"
            value={ticketId || ""}
            onChange={(event) => {
              onSelectTicket(event.target.value);
              setOpen(null);
            }}
          >
            <option value="">Example · Flash sale checkout</option>
            {ids.map((id) => (
              <option key={id}>{id}</option>
            ))}
          </select>
        </label>
        <Tag tone={sample ? "purple" : "green"}>
          {sample ? "Illustrative example" : "Recorded messages"}
        </Tag>
        <button
          className="button secondary"
          onClick={() => onNavigate("communications", ticketId || "")}
        >
          <MessageSquareText size={16} />
          See conversation
        </button>
      </div>
      <div className="decision-layout">
        <Panel className="decision-events">
          <SectionTitle
            title={
              ticket?.title || `${ticketId || "TCK-1042"} · Decision trail`
            }
            detail={`${events.length} published exchanges · times in WIB`}
          />
          {!events.length && (
            <p className="empty-state">
              No recorded messages for this ticket. Persisted audit events are
              available in Ticket history.
            </p>
          )}
          <ol>
            {events.map((event, index) => {
              const expanded = open === event.message_id;
              return (
                <li key={event.message_id}>
                  <span className="decision-number">
                    {event.content?.decision ? (
                      <ShieldCheck size={17} />
                    ) : (
                      index + 1
                    )}
                  </span>
                  <div>
                    <button
                      className="decision-toggle"
                      aria-expanded={expanded}
                      onClick={() =>
                        setOpen(expanded ? null : event.message_id)
                      }
                    >
                      <span>
                        <small>
                          {localTime(event.occurred_at)} WIB · {event.sender}
                        </small>
                        <b>
                          {event.content?.stage
                            ? stageInfo(event.content.stage).label
                            : messageLabel(event.performative)}
                        </b>
                        <p>{messageMeaning(event)}</p>
                      </span>
                      <span>{expanded ? "−" : "+"}</span>
                    </button>
                    {expanded && (
                      <div className="decision-expanded">
                        <p>
                          <b>Shared with:</b> {recipients(event).join(", ")}
                        </p>
                        {event.content?.note && (
                          <blockquote>{event.content.note}</blockquote>
                        )}
                        <OutputSummary
                          output={event.content?.output || event.content}
                        />
                        {Object.keys(event.policy_context || {}).length > 0 && (
                          <p className="policy-inline">
                            Policy: minimum score{" "}
                            {event.policy_context.tau ?? "—"} · maximum risk{" "}
                            {event.policy_context.risk_max ?? "—"}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </Panel>
        <aside>
          <Panel className="decision-policy">
            <ShieldCheck size={25} />
            <h2>When does a person decide?</h2>
            <dl>
              <div>
                <dt>Minimum assessment score</dt>
                <dd>0.70</dd>
              </div>
              <div>
                <dt>Maximum allowed risk</dt>
                <dd>0.60</dd>
              </div>
              <div>
                <dt>Critical impact risk</dt>
                <dd>1.00</dd>
              </div>
            </dl>
            <p>
              A ticket proceeds automatically only when both limits are met.
              Critical impact always needs review.
            </p>
            <p>
              Change and release reviews require a person even when the
              assessment is confident.
            </p>
            <small>
              Sandbox scores are rule or optional model assessments. They are
              not calibrated probabilities.
            </small>
            <button
              className="button secondary"
              onClick={() => onNavigate("history")}
            >
              Open persisted audit history
            </button>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
