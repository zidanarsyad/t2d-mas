import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  Bell,
  Bot,
  CircleHelp,
  FileClock,
  FlaskConical,
  Gauge,
  History,
  LayoutDashboard,
  Menu,
  MessageSquareText,
  Moon,
  Plus,
  Search,
  ShieldCheck,
  Sun,
  Workflow,
  X,
} from "lucide-react";
import { useWorkspace } from "./hooks/useWorkspace";
import { statusLabel } from "./workflow";
const PipelinePage = lazy(() => import("./pages/PipelinePage.jsx"));
const AgentsPage = lazy(() => import("./pages/AgentsPage.jsx"));
const TracePage = lazy(() => import("./pages/TracePage.jsx"));
const ApprovalsPage = lazy(() => import("./pages/ApprovalsPage.jsx"));
const PerformancePage = lazy(() => import("./pages/PerformancePage.jsx"));
const TicketHistoryPage = lazy(() => import("./pages/TicketHistoryPage.jsx"));
const ExperimentsPage = lazy(() => import("./pages/ExperimentsPage.jsx"));
const TicketTestPage = lazy(() => import("./pages/TicketTestPage.jsx"));
const CommunicationsPage = lazy(() => import("./pages/CommunicationsPage.jsx"));
const nav = [
  { id: "pipeline", label: "Ticket overview", icon: LayoutDashboard },
  {
    id: "communications",
    label: "Agent conversations",
    icon: MessageSquareText,
  },
  { id: "test", label: "Run a ticket", icon: Plus },
  { id: "approvals", label: "Human reviews", icon: ShieldCheck },
  { id: "trace", label: "Decision trail", icon: FileClock },
  { id: "history", label: "Ticket history", icon: History },
  { id: "agents", label: "Meet the agents", icon: Bot },
  { id: "performance", label: "Performance example", icon: Gauge },
  { id: "experiments", label: "Experiment results", icon: FlaskConical },
];
const stored = (key, fallback) => {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
};
function route() {
  const id = window.location.hash.slice(1);
  return nav.some((item) => item.id === id) ? id : "communications";
}
function Dialog({ children, title, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const element = ref.current;
    element.showModal();
    return () => element.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="workspace-dialog"
      aria-label={title}
      onCancel={onClose}
      onClick={(event) => event.target === ref.current && onClose()}
    >
      <div className="dialog-heading">
        <h2>{title}</h2>
        <button
          className="icon-btn"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export default function App() {
  const workspace = useWorkspace();
  const [page, setPage] = useState(route),
    [ticketId, setTicketId] = useState(() => stored("t2d-ticket", ""));
  const [theme, setTheme] = useState(() =>
      stored("t2d-theme", "light") === "dark" ? "dark" : "light",
    ),
    [fontSize, setFontSize] = useState(() =>
      stored("t2d-font-size", "standard"),
    );
  const [search, setSearch] = useState(false),
    [help, setHelp] = useState(false),
    [menu, setMenu] = useState(false),
    [query, setQuery] = useState("");
  const record =
    workspace.records.find((item) => item.ticket_id === ticketId) || null;
  const pending = workspace.records.filter(
    (item) => item.status === "waiting_for_review",
  ).length;
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [page]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("t2d-theme", theme);
    } catch {}
  }, [theme]);
  useEffect(() => {
    document.documentElement.dataset.fontSize = fontSize;
    try {
      localStorage.setItem("t2d-font-size", fontSize);
    } catch {}
  }, [fontSize]);
  useEffect(() => {
    const change = () => {
      if (window.location.hash === "#main-content") return;
      setPage(route());
      setMenu(false);
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    const key = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearch((value) => !value);
      }
      if (event.key === "Escape") setMenu(false);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const selectTicket = (id) => {
    setTicketId(id);
    try {
      localStorage.setItem("t2d-ticket", id);
    } catch {}
  };
  const go = (id, nextTicket) => {
    if (nextTicket !== undefined) selectTicket(nextTicket);
    setPage(id);
    window.location.hash = id;
    setSearch(false);
    setMenu(false);
  };
  const matches = workspace.records.filter((item) =>
    `${item.ticket_id} ${item.title} ${item.severity}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const common = {
    records: workspace.records,
    record,
    ticketId,
    onSelectTicket: selectTicket,
    onNavigate: go,
    messages: workspace.messages,
    connected: workspace.connected,
  };
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {menu && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={`sidebar ${menu ? "menu-open" : ""}`}>
        <div className="sidebar-top">
          <div className="brand">
            <span>
              <Workflow size={22} />
            </span>
            <b>
              T2D<i>·</i>MAS<small>From issue to improvement</small>
            </b>
          </div>
          <small className="nav-caption">DELIVERY WORKSPACE</small>
        </div>
        <nav aria-label="Main navigation" className="navigation">
          {nav.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              title={label}
              onClick={() => go(id)}
              className={`nav-link ${page === id ? "active" : ""}`}
              aria-label={label}
              aria-current={page === id ? "page" : undefined}
            >
              <Icon size={19} />
              <span>{label}</span>
              {id === "approvals" && pending > 0 && <b>{pending}</b>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="guardrail-mini">
            <ShieldCheck size={18} />
            <span>
              <b>People stay in control</b>
              <small>Risky decisions pause for review</small>
            </span>
          </div>
          <button
            className="nav-link help"
            onClick={() => {
              setMenu(false);
              setHelp(true);
            }}
            title="How this works"
          >
            <CircleHelp size={19} />
            <span>How this works</span>
          </button>
        </div>
        <div className="prototype-label">COURSE PROJECT · PROTOTYPE</div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div className="crumb">
            <button
              className="icon-btn mobile-menu"
              aria-label="Open navigation"
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              <Menu size={21} />
            </button>
            <span>T2D-MAS</span>
            <i>/</i>
            <b>{nav.find((item) => item.id === page)?.label}</b>
          </div>
          <div className="top-actions">
            <button
              className="search-trigger"
              onClick={() => setSearch(true)}
              aria-label="Search tickets"
            >
              <Search size={17} />
              <span>Find a ticket</span>
              <kbd>Ctrl K</kbd>
            </button>
            <span
              className={`connection ${workspace.connected ? "connected" : ""}`}
            >
              <i />
              {workspace.connected ? "Backend connected" : "Backend offline"}
            </span>
            <button
              className="icon-btn"
              onClick={() => go("approvals")}
              aria-label={`${pending} pending human reviews`}
            >
              <Bell size={18} />
              {pending > 0 && (
                <span className="notification-count">{pending}</span>
              )}
            </button>
            <label className="font-size-control">
              <span>Aa</span>
              <select
                aria-label="Text size"
                value={fontSize}
                onChange={(event) => setFontSize(event.target.value)}
              >
                <option value="standard">Standard</option>
                <option value="large">Large</option>
                <option value="larger">Extra large</option>
              </select>
            </label>
            <button
              className="theme-button"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            >
              {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
            </button>
          </div>
        </header>
        <div id="main-content" className="page-content" tabIndex={-1}>
          <Suspense
            fallback={
              <div className="page-loading" role="status">
                Opening workspace…
              </div>
            }
          >
            {page === "communications" && <CommunicationsPage {...common} />}
            {page === "pipeline" && (
              <PipelinePage
                {...common}
                loading={workspace.loading}
                error={workspace.error}
                onRefresh={workspace.refresh}
              />
            )}
            {page === "test" && (
              <TicketTestPage
                {...common}
                onRecord={(item) => {
                  workspace.upsert(item);
                  selectTicket(item.ticket_id);
                }}
              />
            )}
            {page === "approvals" && (
              <ApprovalsPage
                {...common}
                loading={workspace.loading}
                error={workspace.error}
                onRefresh={workspace.refresh}
                onRecord={workspace.upsert}
              />
            )}
            {page === "agents" && <AgentsPage records={workspace.records} />}{" "}
            {page === "trace" && <TracePage {...common} />}
            {page === "performance" && <PerformancePage />}
            {page === "history" && <TicketHistoryPage {...common} />}
            {page === "experiments" && <ExperimentsPage onNavigate={go} />}
          </Suspense>
        </div>
        <footer className="app-footer">
          <span>Nine specialist stages · Auditable human decisions</span>
          <span>Times in Jakarta (WIB)</span>
        </footer>
      </main>
      {search && (
        <Dialog title="Find a ticket" onClose={() => setSearch(false)}>
          <label className="search-input">
            <Search size={18} />
            <input
              autoFocus
              placeholder="Ticket ID, title, or severity"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="search-results">
            {matches.map((item) => (
              <button
                key={item.ticket_id}
                onClick={() => go("test", item.ticket_id)}
              >
                <span>
                  <b>{item.title}</b>
                  <small>
                    {item.ticket_id} · {statusLabel(item.status)}
                  </small>
                </span>
              </button>
            ))}
            {!matches.length && (
              <p>
                {workspace.loading
                  ? "Loading tickets…"
                  : workspace.error
                    ? "Tickets are unavailable while the backend is offline."
                    : "No matching tickets. Start a new ticket from Run a ticket."}
              </p>
            )}
          </div>
        </Dialog>
      )}
      {help && (
        <Dialog title="How T2D-MAS works" onClose={() => setHelp(false)}>
          <div className="help-content">
            <p>
              Specialist agents pass a ticket through nine stages, from
              receiving an issue to monitoring the proposed improvement.
            </p>
            <ol>
              <li>
                <b>Run a ticket:</b> describe the issue, then follow one step at
                a time or run until review.
              </li>
              <li>
                <b>Agent conversations:</b> see who shares information, how
                workers bid, and why a worker is selected.
              </li>
              <li>
                <b>Human reviews:</b> accept a result, request changes, or stop
                the run. Every decision needs a note.
              </li>
              <li>
                <b>Decision trail & history:</b> inspect the evidence, results,
                and recorded decisions.
              </li>
            </ol>
            <p>
              <b>Prototype scope:</b> investigation uses local rules; changes
              and tests are proposals; releases are simulated. Separate ML,
              graph, and reinforcement learning experiments appear in Experiment
              results.
            </p>
            <p>
              Mobile agents take computation to data and return summaries.
              Static agents work from a fixed location. Meet the agents explains
              each role.
            </p>
            <small>
              Use Ctrl+K to search. Text size and theme controls adjust
              readability.
            </small>
            <label className="help-text-size">
              Text size
              <select
                aria-label="Help text size"
                value={fontSize}
                onChange={(event) => setFontSize(event.target.value)}
              >
                <option value="standard">Standard</option>
                <option value="large">Large</option>
                <option value="larger">Extra large</option>
              </select>
            </label>
          </div>
        </Dialog>
      )}
    </div>
  );
}
