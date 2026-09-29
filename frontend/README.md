# T2D-MAS dashboard

A small React + Tailwind + Recharts control room for the course prototype. It has five screens: pipeline kanban, agent fleet, decision trace, approval inbox, and a 30-day performance report.

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

Vite proxies `/api/*` to `http://localhost:8000` by default. Set `VITE_API_TARGET` to point at a different FastAPI host. Start the backend from the repository root with `docker compose up --build`, then open the Vite URL (normally `http://localhost:5173`). The dashboard listens to `GET /events` through an `EventSource`; the connection badge changes from “Demo mode” to “Live · SSE” when the backend sends its ready event. `EventSource` reconnects after connection loss.

Seeded tickets, trace rows, agent health, approval examples, and the performance chart are deterministic demo data. The approval inbox remains interactive when these demo tickets are not present in the backend; in that case it labels the change as local demo-only. Rejection requires a non-empty reviewer reason. When FastAPI is running, pipeline and approval updates are also broadcast over SSE.

The report exports its displayed trend range as CSV. The Static/Mobile comparison uses the same TCK-1042 incident assumptions from the project report. Theme preference is saved in local storage. Keyboard shortcut `Ctrl/Cmd + K` opens ticket search.

For a production web server, proxy `/api/events` to FastAPI so the browser uses the same origin for SSE.
