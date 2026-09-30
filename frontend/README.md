# T2D-MAS dashboard

A React + Tailwind + Recharts workspace for the course prototype. Nine views explain the ticket journey, agent conversations, interactive ticket runs, human reviews, decision trail, saved history, agent roles, sample performance, and measured experiment results.

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

Vite proxies `/api/*` to `http://localhost:8000` by default. Set `VITE_API_TARGET` to point at a different FastAPI host. Start the backend from the repository root with `docker compose up --build`, then open the Vite URL (normally `http://localhost:5173`). The dashboard subscribes to `GET /events`; EventSource reconnects after connection loss. The backend badge describes this connection only.

Ticket overview, Run a ticket, and Human reviews share `GET /sandbox/tickets` as their source of truth. Reviews use the sandbox review endpoint, require a reviewer name and meaningful note, and fail visibly if the backend cannot save them. A run remains available when switching screens or reloading the browser. Active run state is held by the backend process; after a backend restart, persisted inputs and audit events remain accessible in Ticket history, but old runs cannot be resumed.

Agent conversations and Decision trail show actual messages for the selected ticket, with an explicit illustrative walkthrough available. `GET /messages/history` reads recent Redis messages without consuming or acknowledging worker messages. Recovery merges history with new SSE messages by message ID, in chronological order, up to 500 messages. A selected message stays selected as new messages arrive. Worker bidding inputs and scores in the example follow the report's worked calculation. Monitoring hands its result back to Broker-Triage.

Meet the agents describes the designed Scout, Broker, Worker, and Security roles and configured workflow assignments. It does not fabricate live host health, workloads, or heartbeats. Its Scout-Log control runs the signed mobile-agent demonstration against one of six configured container nodes. Input is synthetic; displayed byte counters cover the backend session.

Performance example is explicitly illustrative, including its DORA cards and static/mobile comparison. Experiment results and evaluation history read saved benchmark result files. Investigation, change preparation, QA, deployment, and monitoring in the interactive workflow remain heuristic, draft, or simulated stages; the separate ML/DL/GNN/RL modules are not composed into this workflow.

The performance example exports its displayed trend range as CSV; Decision trail exports only the selected conversation. Both offer a scoped preview, download, and copy option. Theme, text-size preference, and selected ticket ID are saved locally. Ctrl/Cmd+K opens ticket search. Navigation uses URL fragments and browser back/forward. Smaller screens use a labeled navigation drawer; technical JSON is disclosed on demand.

Run `npm test` for message-recovery and example-consistency checks, and `npm run build` for the production build. See [UI/UX and project alignment](../docs/UI_UX_AND_PROJECT_ALIGNMENT.md) for the screen wireframes and scope mapping.

For a production web server, proxy `/api/events` to FastAPI so the browser uses the same origin for SSE.

The sidebar stays at the viewport top while scrolling, and its brand stays visible during internal navigation scrolling. Small screens use a navigation drawer. The browser tab uses the workflow icon in `public/favicon.svg`. Experiment results use only seed 42, with 100 tickets per arm in the saved bundles; no cross-seed significance or consistency checks are performed.
