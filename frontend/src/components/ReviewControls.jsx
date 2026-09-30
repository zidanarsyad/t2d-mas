import { useState } from "react";
import { Check, RotateCcw, X } from "lucide-react";
import { request } from "../api";
export default function ReviewControls({ record, onRecord }) {
  const [note, setNote] = useState(""),
    [reviewer, setReviewer] = useState("Project reviewer"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function decide(intent) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const next = await request(
        `/sandbox/tickets/${encodeURIComponent(record.ticket_id)}/review`,
        "POST",
        {
          approver: reviewer.trim(),
          approved: intent === "accept",
          intent,
          reason: note.trim(),
        },
      );
      onRecord(next);
      const latest = next.reviews.at(-1);
      setNotice(
        latest?.decision === "clarification_requested"
          ? latest.interpretation?.clarification_question ||
              "Please clarify the requested change."
          : intent === "request_changes"
            ? next.agent_outputs?.[latest?.stage]?.reviewer_override
              ? `Applied the explicit ${next.agent_outputs[latest.stage].reviewer_override} severity correction locally. Continue to submit it for review.`
              : next.agent_outputs?.[latest?.stage]?.fallback_reason
                ? `The model service was unavailable (${next.agent_outputs[latest.stage].fallback_reason}). Inspect the local assessment before continuing.`
                : "The agent revised its proposal. Inspect the result, then continue to review it again."
            : intent === "accept"
              ? "Decision saved. The ticket can continue."
              : "Decision saved. This run is stopped.",
      );
      setNote("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="review-controls">
      <div className="review-guidance">
        <p>
          <b>Accept</b> continues with this proposal. <b>Request changes</b>{" "}
          sends your feedback to the responsible agent. <b>Stop run</b> ends
          this ticket’s workflow.
        </p>
      </div>
      <label>
        Your name
        <input
          maxLength={80}
          value={reviewer}
          onChange={(event) => setReviewer(event.target.value)}
        />
      </label>
      <label>
        Decision note <span>Required</span>
        <textarea
          rows={3}
          maxLength={500}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Explain your decision or the changes the agent should make…"
        />
        <small>{note.length}/500 characters</small>
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="form-notice" role="status">
          {notice}
        </p>
      )}
      <div className="review-buttons">
        <button
          className="button reject"
          disabled={busy || note.trim().length < 3 || !reviewer.trim()}
          onClick={() => decide("reject")}
        >
          <X size={16} />
          Stop run
        </button>
        <button
          className="button secondary"
          disabled={busy || note.trim().length < 3 || !reviewer.trim()}
          onClick={() => decide("request_changes")}
        >
          <RotateCcw size={16} />
          Request changes
        </button>
        <button
          className="button approve"
          disabled={busy || note.trim().length < 3 || !reviewer.trim()}
          onClick={() => decide("accept")}
        >
          <Check size={16} />
          {busy ? "Saving…" : "Accept proposal"}
        </button>
      </div>
    </div>
  );
}
