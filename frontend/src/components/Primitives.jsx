// Small building blocks shared by every page. Severity, status and source are always shown
// as icon + word + colour, so colour is never the only signal.
import { useRef } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  BookOpen,
  CircleAlert,
  CircleCheck,
  CircleDot,
  CirclePlay,
  CircleX,
  Copy,
  Database,
  FlaskConical,
  History,
  Hourglass,
  Info,
  Minus,
  OctagonAlert,
  Radio,
  TriangleAlert,
} from "lucide-react";
import { trendTone } from "../lib/format.js";
import { statusLabel } from "../lib/workflow.js";

export function Panel({ children, className = "", as: Tag = "section", ...rest }) {
  return (
    <Tag className={`panel ${className}`.trim()} {...rest}>
      {children}
    </Tag>
  );
}

/** Page header with a one-line "what you're looking at" and "why it matters". */
export function Heading({ eyebrow, title, what, why, action }) {
  return (
    <header className="page-heading">
      <div className="page-heading-text">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {what && (
          <p className="page-what">
            <b>What you see:</b> {what}
          </p>
        )}
        {why && (
          <p className="page-why">
            <b>Why it matters:</b> {why}
          </p>
        )}
      </div>
      {action && <div className="page-actions">{action}</div>}
    </header>
  );
}

export function SectionTitle({ title, detail, action, level = 2 }) {
  const HeadingTag = `h${level}`;
  return (
    <div className="section-title">
      <div>
        <HeadingTag>{title}</HeadingTag>
        {detail && <p>{detail}</p>}
      </div>
      {action}
    </div>
  );
}

const SEVERITY_ICON = { Critical: OctagonAlert, High: TriangleAlert, Medium: CircleAlert, Low: Info };

/** Null-safe: a missing or "Unknown" severity reads "Not assessed". */
export function Severity({ value }) {
  const known = SEVERITY_ICON[value];
  const Icon = known || CircleDot;
  return (
    <span className={`severity sev-${known ? value.toLowerCase() : "unknown"}`}>
      <Icon size={13} aria-hidden="true" />
      {known ? value : "Not assessed"}
    </span>
  );
}

export function Tag({ children, tone = "neutral", icon: Icon }) {
  return (
    <span className={`tag tag-${tone}`}>
      {Icon && <Icon size={13} aria-hidden="true" />}
      {children}
    </span>
  );
}

const STATUS = {
  running: { icon: CirclePlay, tone: "blue" },
  waiting_for_review: { icon: Hourglass, tone: "amber" },
  completed: { icon: CircleCheck, tone: "green" },
  rejected: { icon: CircleX, tone: "red" },
  duplicate: { icon: Copy, tone: "violet" },
};

export function StatusBadge({ status }) {
  const meta = STATUS[status] || { icon: CircleDot, tone: "neutral" };
  return (
    <Tag tone={meta.tone} icon={meta.icon}>
      {statusLabel(status)}
    </Tag>
  );
}

const SOURCES = {
  live: { label: "Live", icon: Radio, tone: "green", hint: "Data from the running backend" },
  replay: { label: "Replay · illustrative", icon: History, tone: "violet", hint: "Recorded example data, not a live run" },
  simulated: { label: "Simulated by backend", icon: FlaskConical, tone: "amber", hint: "The backend simulated this step with seeded data" },
  model: { label: "Report model", icon: BookOpen, tone: "blue", hint: "Computed from the report's cost model" },
  recorded: { label: "Recorded", icon: Database, tone: "neutral", hint: "Saved by an earlier run" },
};

/** Says where the numbers on screen come from. */
export function SourceBadge({ source = "replay", label }) {
  const meta = SOURCES[source] || SOURCES.replay;
  return (
    <span className={`tag tag-${meta.tone} source-badge`} title={meta.hint}>
      <meta.icon size={13} aria-hidden="true" />
      {label || meta.label}
    </span>
  );
}

/** A KPI card. The arrow shows the direction; the colour and word say whether that is good. */
export function Metric({ label, value, unit, change, goodDirection = "down", note, icon: Icon }) {
  const trend = change ? trendTone(change, { goodDirection }) : null;
  const Arrow = trend?.direction === "up" ? ArrowUpRight : trend?.direction === "down" ? ArrowDownRight : Minus;
  return (
    <Panel className="metric">
      <div className="metric-label">
        <span>{label}</span>
        {Icon && <Icon size={15} aria-hidden="true" />}
      </div>
      <strong className="metric-value">
        {value}
        {unit && <small>{unit}</small>}
      </strong>
      <div className="metric-foot">
        {trend && (
          <span className={`trend trend-${trend.tone}`}>
            <Arrow size={13} aria-hidden="true" />
            {change}
            <span className="visually-hidden">{trend.tone === "good" ? " (better)" : trend.tone === "bad" ? " (worse)" : ""}</span>
          </span>
        )}
        {note && <small>{note}</small>}
      </div>
    </Panel>
  );
}

/** Accessible tabs: arrow keys move between tabs. Render the panel yourself with `tabPanelProps`. */
export function Tabs({ tabs, value, onChange, label, idPrefix = "tab" }) {
  const refs = useRef({});
  const move = (event, index) => {
    const offset = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!offset) return;
    event.preventDefault();
    const next = tabs[(index + offset + tabs.length) % tabs.length];
    onChange(next.id);
    refs.current[next.id]?.focus();
  };
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map((tab, index) => (
        <button
          key={tab.id}
          ref={(element) => (refs.current[tab.id] = element)}
          id={`${idPrefix}-${tab.id}`}
          role="tab"
          type="button"
          className={`tab ${value === tab.id ? "is-selected" : ""}`}
          aria-selected={value === tab.id}
          aria-controls={`${idPrefix}-panel-${tab.id}`}
          tabIndex={value === tab.id ? 0 : -1}
          onClick={() => onChange(tab.id)}
          onKeyDown={(event) => move(event, index)}
        >
          {tab.icon && <tab.icon size={15} aria-hidden="true" />}
          {tab.label}
          {tab.count !== undefined && <span className="tab-count">{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}

export const tabPanelProps = (idPrefix, id) => ({ role: "tabpanel", id: `${idPrefix}-panel-${id}`, "aria-labelledby": `${idPrefix}-${id}` });

export function EmptyState({ icon: Icon = Info, title, children, action }) {
  return (
    <div className="empty-state">
      <Icon size={26} aria-hidden="true" />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

/** A one-line banner: info, ok, warn or bad. */
export function Notice({ tone = "info", icon: Icon = Info, title, children, action, role }) {
  return (
    <div className={`notice notice-${tone}`} role={role}>
      <Icon size={18} aria-hidden="true" />
      <div>
        {title && <b>{title}</b>}
        {children && <p>{children}</p>}
      </div>
      {action}
    </div>
  );
}
