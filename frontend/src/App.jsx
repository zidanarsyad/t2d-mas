import { lazy, Suspense, useEffect, useState } from "react";
import {
  Activity,
  Bell,
  Bot,
  CircleHelp,
  CirclePlay,
  FlaskConical,
  History,
  Kanban,
  LayoutDashboard,
  Menu,
  Moon,
  Radio,
  Route,
  Search,
  ShieldCheck,
  Sun,
  Workflow,
} from "lucide-react";
import { useWorkspace } from "./hooks/useWorkspace";
import Dialog from "./components/Dialog";
import { StatusBadge } from "./components/Primitives";
import { glossary } from "./data/glossary.js";

const OverviewPage = lazy(() => import("./pages/OverviewPage.jsx"));
const RunTicketPage = lazy(() => import("./pages/RunTicketPage.jsx"));
const TicketsPage = lazy(() => import("./pages/TicketsPage.jsx"));
const ReviewsPage = lazy(() => import("./pages/ReviewsPage.jsx"));
const TracePage = lazy(() => import("./pages/TracePage.jsx"));
const AgentsPage = lazy(() => import("./pages/AgentsPage.jsx"));
const MonitoringPage = lazy(() => import("./pages/MonitoringPage.jsx"));
const ExperimentsPage = lazy(() => import("./pages/ExperimentsPage.jsx"));

const NAV = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, page: OverviewPage },
  { id: "run", label: "Run a ticket", icon: CirclePlay, page: RunTicketPage },
  { id: "tickets", label: "Tickets", icon: Kanban, page: TicketsPage },
  { id: "reviews", label: "Human reviews", icon: ShieldCheck, page: ReviewsPage },
  { id: "trace", label: "Decision trace", icon: Route, page: TracePage },
  { id: "agents", label: "Agents", icon: Bot, page: AgentsPage },
  { id: "monitoring", label: "Monitoring", icon: Activity, page: MonitoringPage },
  { id: "experiments", label: "Experiment results", icon: FlaskConical, page: ExperimentsPage },
];

// Old bookmarks and the demo guide still use these hashes.
export const legacyRoutes = {
  test: "run",
  pipeline: "tickets",
  history: "tickets/saved",
  approvals: "reviews",
  communications: "trace",
  performance: "monitoring",
};

function readRoute() {
  const raw = window.location.hash.slice(1);
  // An old hash is rewritten in place, so the address bar shows the new name.
  if (legacyRoutes[raw]) window.history.replaceState(null, "", `#${legacyRoutes[raw]}`);
  const [page, sub = ""] = (legacyRoutes[raw] || raw).split("/");
  return NAV.some((item) => item.id === page) ? { page, sub } : { page: "overview", sub: "" };
}

const stored = (key, fallback) => {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
};
const store = (key, value) => {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* Private windows may block storage; the setting then lasts for this visit only. */
  }
};
const systemTheme = () => (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");

function healthText(health) {
  if (!health) return "The backend is not reachable. Pages show recorded and illustrative data, and say so.";
  const parts = [`Mode: ${health.mode || "unknown"}`];
  if (health.storage?.kind) parts.push(`storage: ${health.storage.kind}`);
  if (health.bus?.kind) parts.push(`bus: ${health.bus.kind}`);
  if (health.nodes?.kind) parts.push(`nodes: ${health.nodes.kind}`);
  parts.push(`triage model: ${health.triage_llm?.enabled ? "free OpenRouter model" : "local rules"}`);
  return parts.join(" · ");
}

export default function App() {
  const workspace = useWorkspace();
  const [route, setRoute] = useState(readRoute);
  const [ticketId, setTicketId] = useState(() => stored("t2d-ticket", ""));
  const [theme, setTheme] = useState(() => stored("t2d-theme", systemTheme()));
  const [fontSize, setFontSize] = useState(() => stored("t2d-font-size", "standard"));
  const [dialog, setDialog] = useState(null); // "search" | "help" | null
  const [menu, setMenu] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    store("t2d-theme", theme);
  }, [theme]);
  useEffect(() => {
    document.documentElement.dataset.fontSize = fontSize;
    store("t2d-font-size", fontSize);
  }, [fontSize]);
  useEffect(() => {
    const onHash = () => {
      if (window.location.hash === "#main-content") return;
      setRoute(readRoute());
      setMenu(false);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [route.page]);
  useEffect(() => {
    const onKey = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setDialog((value) => (value === "search" ? null : "search"));
      }
      if (event.key === "Escape") setMenu(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const selectTicket = (id) => {
    setTicketId(id || "");
    store("t2d-ticket", id || "");
  };
  /** Go to a view; `nextTicket` (optional) selects a ticket first. */
  const navigate = (id, nextTicket) => {
    if (nextTicket !== undefined) selectTicket(nextTicket);
    window.location.hash = id;
    setRoute(readRoute());
    setDialog(null);
    setMenu(false);
  };

  const current = NAV.find((item) => item.id === route.page) || NAV[0];
  const Page = current.page;
  const live = workspace.mode === "live";
  const matches = workspace.records.filter((item) => `${item.ticket_id} ${item.title} ${item.severity}`.toLowerCase().includes(query.toLowerCase()));
  const groups = [...new Set(glossary.map((entry) => entry.group))];

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {menu && <button type="button" className="nav-scrim" aria-label="Close navigation" onClick={() => setMenu(false)} />}
      <aside className={`sidebar ${menu ? "is-open" : ""}`}>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Workflow size={20} />
          </span>
          <span>
            <b>T2D·MAS</b>
            <small>From feedback to release</small>
          </span>
        </div>
        <nav aria-label="Main navigation" className="nav">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button" onClick={() => navigate(id)} className={`nav-link ${route.page === id ? "is-active" : ""}`} aria-current={route.page === id ? "page" : undefined}>
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
              {id === "reviews" && workspace.pendingCount > 0 && (
                <b className="nav-count" aria-label={`${workspace.pendingCount} waiting`}>
                  {workspace.pendingCount}
                </b>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="guardrail">
            <ShieldCheck size={17} aria-hidden="true" />
            <span>
              <b>People stay in control</b>
              <small>Merges and full releases always need a human.</small>
            </span>
          </div>
          <button
            type="button"
            className="nav-link"
            onClick={() => {
              setMenu(false);
              setDialog("help");
            }}
          >
            <CircleHelp size={18} aria-hidden="true" />
            <span>How this works</span>
          </button>
          <p className="prototype-label">Course prototype · UGM</p>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="crumb">
            <button type="button" className="icon-button menu-button" aria-label="Open navigation" aria-expanded={menu} onClick={() => setMenu(!menu)}>
              <Menu size={20} />
            </button>
            <span className="crumb-root">
              T2D-MAS <span aria-hidden="true">/</span>
            </span>
            <b>{current.label}</b>
          </div>
          <div className="top-actions">
            <button type="button" className="search-trigger" onClick={() => setDialog("search")} aria-label="Find a ticket (Ctrl+K)">
              <Search size={16} aria-hidden="true" />
              <span>Find a ticket</span>
              <kbd>Ctrl K</kbd>
            </button>
            <span className={`mode-badge ${live ? "is-live" : "is-replay"}`} title={healthText(workspace.health)} tabIndex={0} aria-label={`${live ? "Live" : "Replay mode"}. ${healthText(workspace.health)}`}>
              {live ? <Radio size={14} aria-hidden="true" /> : <History size={14} aria-hidden="true" />}
              <span className="mode-text">{live ? `Live${workspace.health?.mode === "local" ? " · local" : ""}` : "Replay mode"}</span>
            </span>
            <button type="button" className="icon-button" onClick={() => navigate("reviews")} aria-label={`${workspace.pendingCount} tickets waiting for a human`}>
              <Bell size={18} />
              {workspace.pendingCount > 0 && <span className="bell-count">{workspace.pendingCount}</span>}
            </button>
            <label className="text-size">
              <span aria-hidden="true">Aa</span>
              <select aria-label="Text size" value={fontSize} onChange={(event) => setFontSize(event.target.value)}>
                <option value="standard">Standard</option>
                <option value="large">Large</option>
                <option value="larger">Extra large</option>
              </select>
            </label>
            <button type="button" className="icon-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </div>
        </header>
        <main id="main-content" className="content" tabIndex={-1}>
          <Suspense
            fallback={
              <p className="page-loading" role="status">
                Opening…
              </p>
            }
          >
            <Page key={current.id} workspace={workspace} ticketId={ticketId} onSelectTicket={selectTicket} onNavigate={navigate} sub={route.sub} />
          </Suspense>
        </main>
        <footer className="footer">
          <span>Nine agent stages · six human gates · append-only audit log</span>
          <span>Times in Jakarta (WIB)</span>
        </footer>
      </div>

      {dialog === "search" && (
        <Dialog title="Find a ticket" onClose={() => setDialog(null)}>
          <label className="search-input">
            <Search size={17} aria-hidden="true" />
            <input autoFocus aria-label="Ticket id, title or severity" placeholder="Ticket id, title or severity" value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <div className="search-results">
            {matches.map((item) => (
              <button key={item.ticket_id} type="button" className="search-result" onClick={() => navigate("run", item.ticket_id)}>
                <b>{item.title}</b>
                <span>
                  {item.ticket_id} <StatusBadge status={item.status} />
                </span>
              </button>
            ))}
            {!matches.length && (
              <p className="muted">{workspace.loading ? "Loading tickets…" : !live ? "No live tickets: the backend is not reachable." : "No matching tickets. Start one from Run a ticket."}</p>
            )}
          </div>
        </Dialog>
      )}
      {dialog === "help" && (
        <Dialog title="How T2D-MAS works" onClose={() => setDialog(null)} className="dialog-wide">
          <div className="stack help">
            <p>
              Nine agents pass a ticket from user feedback to a monitored release. Agents act alone only when the policy allows it; six human gates catch the rest, and every step is written to an
              append-only audit log.
            </p>
            <ol>
              <li>
                <b>Overview</b> replays one flash-sale incident from start to finish.
              </li>
              <li>
                <b>Run a ticket</b> starts a real run from the feedback inbox and animates it live.
              </li>
              <li>
                <b>Tickets</b> shows where every ticket is; <b>Human reviews</b> lists what waits for you.
              </li>
              <li>
                <b>Decision trace</b> explains why each decision was made, step by step.
              </li>
              <li>
                <b>Agents</b>, <b>Monitoring</b> and <b>Experiment results</b> explain the roles, the release health loop and the A0–A3 comparison.
              </li>
            </ol>
            <p className="muted">
              <b>Replay mode:</b> without the backend, pages use recorded or illustrative data and label it. Animations follow your system&apos;s reduced-motion setting. Ctrl+K finds a ticket.
            </p>
            <h3>Glossary</h3>
            {groups.map((group) => (
              <section key={group} className="glossary-group">
                <h4>{group}</h4>
                <dl className="glossary">
                  {glossary
                    .filter((entry) => entry.group === group)
                    .map((entry) => (
                      <div key={entry.id}>
                        <dt>{entry.term}</dt>
                        <dd>
                          {entry.short}
                          {entry.example && <span className="muted"> Example: {entry.example}</span>}
                        </dd>
                      </div>
                    ))}
                </dl>
              </section>
            ))}
          </div>
        </Dialog>
      )}
    </div>
  );
}
