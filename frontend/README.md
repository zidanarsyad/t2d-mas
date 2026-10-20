# T2D-MAS dashboard

A React 19 + Vite 7 dashboard for the course prototype. Lucide icons and Recharts are the only
runtime libraries; styling is one plain CSS file (Tailwind was removed). It shows how nine agents
move a ticket from user feedback to a monitored release, and where people decide.

## Run it

```powershell
# Backend (repository root, local mode: memory storage, memory bus, in-process nodes)
python -m uvicorn agents.app:app --port 8000

# Dashboard
cd frontend
npm install
npm run dev
```

Vite proxies `/api/*` to `http://127.0.0.1:8000` (set `VITE_API_TARGET` for another host) and
serves the dashboard on `http://localhost:5173`. Without the backend the dashboard still works in
**replay mode** (see below).

```powershell
npm test        # node --test "src/**/*.test.js"
npm run build   # production build in dist/
```

In the Claude desktop app, `.claude/launch.json` at the repository root starts both servers
(`backend` and `dashboard`).

Good to know for a demo:

- Local mode keeps everything in memory, so a backend restart starts with an empty board.
- The inbox shows ten messages at a time; **Show other messages** draws another set from the
  backend's pool (the OTP pair FB-011/FB-012 is the "a person decides" duplicate example).
- Without `OPENROUTER_API_KEY`, triage uses local rules. A change request at the impact gate then
  needs an explicit correction such as "severity should be High"; otherwise the agent asks for a
  clearer note, and its question stays above the review form until you answer.
- Demo options on the start form: a planted test secret (the secret scan must stop it) and a
  shipped regression (monitoring must open a follow-up ticket, which appears on the Board).
- If the inbox request fails while the badge says Live (for example, the backend is still
  starting), the page retries three times, 1.5 s apart, before it shows the offline sample.
- The dev proxy opens a new connection for every request (`vite.config.js`). uvicorn closes idle
  connections after 5 s, and reusing a closed one would fail the request with a 500.
- The dev proxy targets `127.0.0.1`, not `localhost`. uvicorn listens on IPv4 only, but Node tries
  `localhost` over IPv6 first. A Docker stack of this project that restarts in a loop answers there
  for a few seconds each time, and those requests failed with "The backend is not reachable".

## The eight views

Each view starts with one line on *what you see* and *why it matters*. Old links still work: the
hashes in the right-hand column are rewritten to the new ones.

| View | Hash | What it answers | Old hashes |
|---|---|---|---|
| Overview | `#overview` | What is T2D-MAS? An animated replay of the TCK-1042 flash-sale story, the nine stages, and an idea-vs-prototype table | — |
| Run a ticket | `#run` | What happens to one piece of feedback? Feedback inbox (Indonesian + English) → start → live animated journey → each agent's five components → review at the gate | `#test` |
| Tickets | `#tickets` | Where is the work, and what is blocked? A nine-column **Board** (severity, agent, time in stage, "Waiting for a human") and **Saved runs** from the audit log | `#pipeline`, `#history` |
| Human reviews | `#reviews` | What needs my decision? Queue sorted by severity risk × minutes waiting, value-vs-limit evidence, Approve / Request changes / Reject and stop, and the six-gate table | `#approvals` |
| Decision trace | `#trace` | Why was this decided? A seekable animated flow plus a timeline; selecting a row jumps the flow to that step; JSON export | `#communications` |
| Agents | `#agents` | Who does what? Family, mobile or static, live load, the five components, and the Scout-Log trip with a byte counter | — |
| Monitoring | `#monitoring` | Is the release healthy, and how does an alert become a ticket? Telemetry playback with the SLO line, alert → follow-up ticket, canary bar, illustrative DORA report with CSV | `#performance` |
| Experiment results | `#experiments` | What did A0–A3 measure? **Results** (one metric list, each marked measured / scored / simulated) and **Sample tickets** | — |

The top bar has ticket search (Ctrl+K), the Live/Replay badge (hover it for storage, bus, node and
triage-model details from `/health`), the review bell, text size and the light/dark switch.
**How this works** lists the views and the full glossary; glossary words in the pages
(dotted underline) open a short explanation on hover, focus or tap.

## Live and replay mode

The badge says **Live** when the event stream (`GET /events`) is connected or `/health` answers;
otherwise **Replay mode**. A 404 or 503 from a newer endpoint counts as "not available" too, so the
page falls back instead of failing. Every animated or numeric panel carries a source label:

| Label | Meaning |
|---|---|
| Live | Data from the running backend |
| Simulated by backend | The backend produced it with seeded simulators (telemetry, CI, deploys) |
| Replay · illustrative | Recorded example data in `src/data/`, not a live run |
| Report model | Computed from the report's cost model (mobile vs static) |
| Recorded | Read back from the saved audit log |

What each view does without the backend:

- **Overview** and **Decision trace** replay the illustrative TCK-1042 conversation (`data/sampleConversation.js`, 23 steps, about 26 s at 1×).
- **Run a ticket** shows the offline inbox (`data/mockFeedback.js`); starting a run needs the backend, and **Watch a recorded run** plays the TCK-1042 replay with each stage's designed components.
- **Tickets** shows one illustrative card (TCK-1042 waiting for its release sign-off).
- **Human reviews** explains the six gates with the fallback policy.
- **Agents** plays the report model: 6 nodes × 1,365 MB; mobile moves 84 MB in about 27 s, static pulls 8,190 MB in about 655 s.
- **Monitoring** generates the same seeded hour in the browser (`data/monitoringScenario.js`); a follow-up ticket is simulated (TCK-1043).
- **Experiment results** explains the four designs; saved numbers need the backend.

When the stream comes back, the dashboard reconnects by itself (EventSource retries network errors;
the hook reopens the stream after HTTP errors with a growing delay).

## Motion settings

- Animations are CSS keyframes inside a step; the step itself is chosen by a small player
  (`useStepPlayer`: play, pause, previous, next, restart, speed 0.5× / 1× / 2×, scrub slider).
  The resting style of every moving part is its end state, and `key={frame.id}` restarts the motion per step.
- Only the Overview replay starts by itself. Players pause when the browser tab is hidden.
- With **prefers-reduced-motion: reduce** (set in the operating system):
  nothing starts by itself, CSS turns every animation and transition off (each step shows its end
  state, with a trail arrow showing who sent what), counters jump to their value, the telemetry
  chart shows the whole hour at once, and every step stays reachable with the buttons or slider.
- Each animation has a text version: an `aria-live` caption per step (silent while playing), a
  hidden list of stage states, the trip log per node, and the anomaly and canary steps as text.
- Severity, gate and status always show an icon and a word, never colour alone.

## How the code is organised

```
src/
  App.jsx        shell: 8-item navigation, legacy hash aliases, top bar, search and help dialogs
  api.js         the only file that calls fetch(); request(), api.*, isUnavailable()
  styles.css     tokens (light + dark), text size, reset, base, layout, components, animations, pages
  lib/           pure JS (no React or DOM), tested with node --test
    workflow.js    the one list of stages, gates, labels, normalizeSnapshot
    policy.js      DEFAULT_POLICY fallback, normalizePolicy, gateOutcome, duplicateBand, canaryAllowed,
                   reviewPriority, gateEvidence, gateRule
    flow.js        layout, agent anchors, frames from messages or a snapshot, replay frames
    mobileTrip.js  report cost model, ring geometry, trips from snapshots, migrations or events
    telemetry.js   normalizeTelemetry, pivotSeries, detectAnomalies, canaryAt, sloStatus
    trace.js       one entry shape for live messages and saved audit events
    feedback.js    channels, language labels, normalizeFeedback
    format.js      WIB times, numbers, bytes, durations, run labels, trend tone, bar widths, metric names
  data/          illustrative content only (sample story, offline inbox, monitoring scenario, agents,
                 report examples, glossary)
  hooks/         useWorkspace, useLiveEvents, useReducedMotion, useStepPlayer, useLiveFlow, useCountUp, useNow
  components/    Primitives, Dialog, ExportDialog, Term, OutputSummary, ReviewControls, GateEvidence,
                 PlayerControls, PipelineFlow, MobileAgentMap, MonitoringBoard, TraceTimeline, BidTable,
                 StageDetails, FeedbackCard
  pages/         OverviewPage, RunTicketPage, TicketsPage, ReviewsPage, TracePage, AgentsPage,
                 MonitoringPage, ExperimentsPage
```

Rules the tests enforce (`src/guards.test.js`, `src/styles.test.js`):

- only `api.js` calls `fetch`, and only `hooks/useLiveEvents.js` opens an `EventSource`;
- pages and components contain no policy thresholds: τ, R_max, duplicate bands and the canary limit come from `GET /policy`, with `DEFAULT_POLICY` (in `lib/policy.js`) as the offline fallback;
- every CSS class is used, every JSX class has a rule, and hex colours appear only in the token blocks;
- Tailwind stays out of `package.json`, `vite.config.js` and `styles.css`.

Backend field names stay snake_case; the `normalize*` adapters in `lib/` absorb small differences
in the API. Text size (Standard 13.5 px, Large 15.3 px, Extra large 17.1 px root size), theme and
the selected ticket are remembered in `localStorage`. Times are shown in Jakarta time (WIB).

## Endpoints used

`GET /health`, `GET /policy`, `GET /events` (SSE), `GET /messages/history`,
`GET /feedback/inbox`, `POST /sandbox/tickets`, `GET /sandbox/tickets`, `GET /sandbox/tickets/{id}`,
`POST /sandbox/tickets/{id}/advance`, `POST /sandbox/tickets/{id}/review`, `POST /demo/migrate/{node}`,
`GET /monitoring/telemetry`, `POST /monitoring/anomalies/{id}/ticket`, `GET /experiments`,
`GET /history`, `GET /ticket-history`. For production, proxy `/api/*` (including the event stream)
to FastAPI on the same origin.
