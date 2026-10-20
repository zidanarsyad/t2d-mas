// Feedback channels and inbox items (the shape of GET /feedback/inbox).

export const CHANNELS = [
  { id: "app_store_review", label: "App store review" },
  { id: "email", label: "Email" },
  { id: "portal_form", label: "Support portal" },
  { id: "cs_chat", label: "Customer-service chat" },
  { id: "slack", label: "Slack" },
  { id: "crash_reporter", label: "Crash reporter" },
  { id: "manual", label: "Typed by hand" },
  { id: "monitoring", label: "Monitoring alert" },
];

export function channelLabel(id) {
  const found = CHANNELS.find((channel) => channel.id === id);
  if (found) return found.label;
  return id ? String(id).replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase()) : "Other channel";
}

export function languageLabel(code) {
  return { id: "Bahasa Indonesia", en: "English", mixed: "Indonesian + English" }[code] || "Unknown language";
}

// Common Indonesian words in casual feedback; enough to set the `lang` attribute offline.
const INDONESIAN_CUES =
  /\b(aku|saya|nggak|gak|tidak|tolong|udah|sudah|pas|kak|gimana|banget|aplikasi|halaman|tombol|gagal|terus|kok|bisa|dan|yang|di|ini|itu|lagi|mohon|pesanan|saldo)\b/gi;

/** "id", "en" or "mixed" from the share of Indonesian cue words. */
export function guessLanguage(text) {
  const words = String(text || "").match(/[A-Za-zÀ-ÿ']+/g) || [];
  if (!words.length) return "en";
  const cues = (String(text).match(INDONESIAN_CUES) || []).length;
  const share = cues / words.length;
  if (share >= 0.12) return "id";
  if (share >= 0.04) return "mixed";
  return "en";
}

/** Fill the fields the inbox needs; unknown channels and missing titles are tolerated. */
export function normalizeFeedback(item) {
  const value = item && typeof item === "object" ? item : {};
  const text = String(value.text || value.body || "");
  return {
    feedback_id: value.feedback_id || value.id || null,
    channel: value.channel || "manual",
    author: value.author || "Anonymous user",
    received_at: value.received_at || null,
    title: value.title || null,
    text,
    metadata: value.metadata && typeof value.metadata === "object" ? value.metadata : {},
    language: value.language || guessLanguage(text),
  };
}
