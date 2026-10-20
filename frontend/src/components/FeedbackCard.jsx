import { Bug, Mail, MessageSquareText, MessagesSquare, PenLine, Siren, Star, Store } from "lucide-react";
import { channelLabel, languageLabel, normalizeFeedback } from "../lib/feedback.js";
import { formatTime } from "../lib/format.js";

const CHANNEL_ICONS = {
  app_store_review: Store,
  email: Mail,
  portal_form: PenLine,
  cs_chat: MessagesSquare,
  slack: MessageSquareText,
  crash_reporter: Bug,
  monitoring: Siren,
};

/** One message from the feedback inbox, rendered with its language so screen readers read it right. */
export default function FeedbackCard({ item, selected = false, onSelect }) {
  const feedback = normalizeFeedback(item);
  const Icon = CHANNEL_ICONS[feedback.channel] || MessageSquareText;
  const meta = feedback.metadata;
  const body = (
    <>
      <span className="feedback-top">
        <span className="feedback-channel">
          <Icon size={14} aria-hidden="true" />
          {channelLabel(feedback.channel)}
        </span>
        <time>{formatTime(feedback.received_at, { date: true, seconds: false })}</time>
      </span>
      {feedback.title && <b className="feedback-title">{feedback.title}</b>}
      <span className="feedback-text" lang={feedback.language === "en" ? "en" : "id"}>
        {feedback.text}
      </span>
      <span className="feedback-meta">
        <span>{feedback.author}</span>
        <span className="tag tag-neutral">{languageLabel(feedback.language)}</span>
        {meta.rating !== undefined && (
          <span className="rating" aria-label={`${meta.rating} out of 5 stars`}>
            <Star size={12} aria-hidden="true" /> {meta.rating}/5
          </span>
        )}
        {meta.app_version && <span>v{meta.app_version}</span>}
        {meta.platform && <span>{meta.platform}</span>}
      </span>
    </>
  );
  if (!onSelect) return <div className="feedback-card">{body}</div>;
  return (
    <button type="button" className={`feedback-card ${selected ? "is-selected" : ""}`} aria-pressed={selected} onClick={() => onSelect(item)}>
      {body}
    </button>
  );
}
