import { useState } from "react";
import { Check, MessageCircleQuestion, RotateCcw, X } from "lucide-react";
import { api } from "../api";
import { clarificationQuestion, INTENTS, intentEffects, intentLabel } from "../lib/workflow.js";
import { Notice } from "./Primitives";

const ICONS = { accept: Check, request_changes: RotateCcw, reject: X };
const BUTTON_CLASS = { accept: "button button-approve", request_changes: "button", reject: "button button-reject" };

/**
 * Approve / Request changes / Reject and stop. Only the intents the backend allows at this
 * gate are enabled (a leaked secret can never be approved). A name and a reason are required.
 * The page reports the outcome; an open question from the agent is read from the ticket itself,
 * so it stays visible until the reviewer answers.
 */
export default function ReviewControls({ record, onRecord }) {
  const gate = record?.pending_gate?.gate || record?.waiting_for;
  const allowed = record?.pending_gate?.allowed_intents || INTENTS;
  const question = clarificationQuestion(record);
  const [reason, setReason] = useState("");
  const [reviewer, setReviewer] = useState("Project reviewer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const ready = !busy && reason.trim().length >= 3 && reviewer.trim().length > 0;

  async function decide(intent) {
    setBusy(true);
    setError("");
    try {
      const next = await api.review(record.ticket_id, { approver: reviewer.trim(), approved: intent === "accept", intent, reason: reason.trim() });
      onRecord(next, intent);
      setReason("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="review-controls">
      {question && (
        <Notice tone="warn" icon={MessageCircleQuestion} title="The agent needs a clearer note" role="status">
          {question}
        </Notice>
      )}
      <ul className="intent-list">
        {INTENTS.map((intent) => (
          <li key={intent} className={allowed.includes(intent) ? "" : "is-disabled"}>
            <b>{intentLabel[intent]}:</b>{" "}
            {!allowed.includes(intent) ? <em>not possible at this gate.</em> : intent === "reject" ? "Stop this run here." : intentEffects[gate]?.[intent] || "Continue."}
          </li>
        ))}
      </ul>
      <div className="form-grid">
        <label className="field">
          <span>Your name</span>
          <input maxLength={80} value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
        </label>
        <label className="field">
          <span>
            Reason <em className="required">required</em>
          </span>
          <textarea
            rows={3}
            maxLength={500}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Why do you decide this? For a change request, say what the agent should do differently."
          />
          <small>{reason.length}/500</small>
        </label>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="button-row review-buttons">
        {[...INTENTS].reverse().map((intent) => {
          const Icon = ICONS[intent];
          return (
            <button key={intent} type="button" className={BUTTON_CLASS[intent]} disabled={!ready || !allowed.includes(intent)} onClick={() => decide(intent)}>
              <Icon size={16} aria-hidden="true" />
              {busy ? "Saving…" : intentLabel[intent]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
