# T2D-MAS live demo guide

This walkthrough takes 5–8 minutes. It follows one real user complaint from the feedback inbox
to a monitored release. It shows:
- the agents handing work to each other;
- the Contract Net auction;
- the mobile agent's trip to the data nodes;
- the human gates;
- the feedback loop from monitoring back to triage.

Planning, implementation, QA, deployment and monitoring use seeded simulators, and the dashboard
says so on every panel. No real repository, CI, cluster or telemetry is connected.

## Prepare (no Docker needed)

Use two terminals, both starting in the repository root.

```powershell
python -m uvicorn agents.app:app --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.
- The top bar should say **Live**. Hover the badge: it should show memory storage, a memory bus and in-process nodes (local mode).
- Leave `OPENROUTER_API_KEY` unset. Triage then uses its local rules, which makes the demo repeatable.
- Local mode keeps everything in memory, so restarting the backend gives you an empty board.
- If the backend is not running, these views still play their recorded or simulated versions: Overview, Decision trace, Agents and Monitoring.

To use the full Docker stack instead (Redis, PostgreSQL, six node containers), run `docker compose up --build`. After a database schema change, run `docker compose down -v` once.

## Walkthrough

| Step | Do this | Say this |
|---|---|---|
| 1 | **Overview**: let the TCK-1042 replay play. | The flash-sale story moves through the nine stages: 2,143 crash reports become one ticket, which goes through triage, the squad auction, the mobile investigation, merge review and release sign-off. Monitoring then closes the loop back to triage. The table below the replay shows what is real, mixed or simulated. |
| 2 | **Run a ticket** → pick the crash report "Aplikasi langsung nutup sendiri pas aku pencet Bayar…" → **Start this ticket**. | It is real user language: casual Indonesian with a typo, an emoji and an app version. Scout-Feedback masks personal data, detects the language, derives a title, reads version 4.18.2 and Android, and files it under *payment*. |
| 3 | **Run until a human is needed**. | Triage finds no earlier duplicate and rates it **Critical**: the balance was deducted but there is no order. Critical risk (1.0) is above R_max (0.60), so the autonomy gate stops for a person. Open the stage to show the agent's five steps: perceive, remember, reason, act, report. |
| 4 | Enter your name and a note → **Approve**. Then **Run until a human is needed** again. | Watch the auction: three squads bid, and **Payments** wins on skill and load. That squad then investigates. Scout-Log visits the six nodes: five run the signed analysis code, while node-6 holds only 30 MB and uses its exporter. Only aggregates come back, and the ranking points to **payment-db**. Planning writes Given/When/Then criteria, the draft change passes the secret scan, and QA runs about 120 of 3,400 tests within 8 minutes. |
| 5 | At **Review the proposed change** → **Approve**. | Merging is irreversible, so it always needs a person. The merge runs only now, and it is recorded with your name. |
| 6 | **Run until a human is needed**. | Deployment computes a release risk score. At 0.30 or less the 5% canary starts by itself; above that it first stops at **Approve the 5% canary**. The full release always stops at **Approve the full release**. |
| 7 | **Approve** the release, then finish the run. | Monitoring checks the service against its SLO baseline for 30 simulated minutes, finds it healthy and closes the ticket. |
| 8 | Back in **Run a ticket**, start the app-store review that repeats the same complaint (FB-002). | It is a near-identical repost, with similarity at or above 0.85, so triage links it to the first ticket and closes it; later stages are skipped. Optionally, start FB-011 and then FB-012, two wordings of "OTP tidak masuk". They score between 0.70 and 0.85, so a person decides in **Human reviews**. |
| 9 | **Decision trace** → select your ticket → drag the slider or select a timeline row. | Every handoff, bid, gate (with τ and R_max) and human decision is in the audit log, and the flow jumps to the selected step. You can export it as JSON. |
| 10 | **Agents** → **Investigate on the real nodes**, then switch between **Static pull** and **Mobile agent**. | The live trip shows real bytes per node. The report's cost model compares 8,190 MB in about 655 s for a static pull with 84 MB in about 27 s for the mobile agent. The 42 MB break-even explains node-6. |
| 11 | **Monitoring** → play the flash-sale hour → **Open a follow-up ticket**. | payment-db breaks its SLO at minute 20. The alert becomes a new ticket that enters at Feedback capture: the feedback loop. It appears on the **Tickets** board. The canary bar shows 5% → 25% → 50% → 100%, and the last step needs a human. |
| 12 | **Experiment results**. | These are the A0–A3 numbers the report cites: 5 seeds × 100 tickets. Point out the caveat: the generated tickets contain their severity word, so severity accuracy is 1.0 everywhere (see `docs/AUDIT.md`). |

## Optional demos

**The secret scan.** Before starting a ticket, tick **Put a test secret in the draft change**.
- The run stops at the secret scan, and Approve is disabled.
- **Request changes** makes Worker-Impl redraft the change without the key; the scan then passes.

**The feedback loop inside one run.** Tick **Ship a regression**.
- After the release, monitoring sees the regression and opens a follow-up ticket by itself.

**Changing the triage decision.** At the impact gate, use **Request changes** with an explicit correction, for example *"Only one region is affected; severity should be High."*
- Without an OpenRouter key, an unclear note makes the agent ask a clarifying question.
- That question stays above the review form until you answer it.

**Rejecting.** **Reject and stop** ends a run for good; start a new ticket to try again.

## Troubleshooting

- **The badge says Replay mode.** The backend is not reachable. Start it, and the dashboard reconnects by itself.
- **Port 8000 is busy.** Start the backend with `--port 8001`. Set `$env:VITE_API_TARGET = "http://localhost:8001"` before `npm run dev`.
- **The board is empty after a restart.** This is expected in local mode, because everything is in memory. Docker mode keeps the audit history in PostgreSQL.
- **Stopping.** Press Ctrl+C in both terminals. With Docker, use `docker compose down`, and add `-v` only if you also want to drop the database and the signing keys.
