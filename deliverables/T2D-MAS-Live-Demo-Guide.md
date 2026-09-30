# T2D-MAS Live Demo Guide

This walkthrough shows agent handoffs, worker bidding, three human checkpoints, and saved decisions. Allow 5–8 minutes. Investigation is heuristic; implementation, QA, release, and monitoring produce drafts or simulations. No repository, CI, production deployment, or live telemetry is connected.

## Prepare

From the repository root, start Docker Desktop and run:

```powershell
$env:OPENROUTER_API_KEY = ""
docker compose up --build
```

Leaving the key empty selects local rule-based triage. In another terminal, from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open the printed Vite URL, normally `http://localhost:5173`. Verify `http://localhost:8000/health` and the **Backend connected** badge. The badge indicates event-stream connectivity. The sidebar stays at the viewport top; small screens use a navigation drawer. Font size and theme controls support presentation visibility.

One browser tab is enough: navigation and refresh recover active runs from the backend. A backend restart preserves audit history but does not restore resumable runs. The conversation screen recovers up to 500 recent Redis messages without consuming the worker queue.

## Walkthrough

| Step | Action | Explain |
| --- | --- | --- |
| 1 | Open **Agent conversations** and select the labeled example. Select a handoff and inspect the worker bids. | The example illustrates requests, bids, worker selection, shared results, and monitoring feedback. Protocol fields and raw payloads are available under technical details. The example is distinct from a recorded ticket. |
| 2 | Open **Run a ticket**, click **Use sample issue**, then **Start ticket**. | The editable checkout issue includes data corruption. Local triage assigns Critical, whose risk exceeds 0.60 and requires review. A unique `TEST-…` reference links input, outputs, messages, and decisions. |
| 3 | Click **Run until review**. | The workflow stops at **Confirm the impact assessment**. Autonomy requires confidence at least 0.70 and risk no more than 0.60. Automatic progression does not approve a checkpoint. |
| 4 | Enter a reviewer name and a meaningful note, then click **Accept proposal**. | The decision is saved with the reviewer and feedback. Approval clears this checkpoint only. |
| 5 | Click **Run until review** again; use **See conversation** to inspect the selected ticket’s actual handoffs and bids. Return to **Run a ticket**. | Assignment compares skill, capacity, and cost. The winning worker shares investigation, planning, and change drafts with the next agents. Navigation preserves the run. |
| 6 | At **Review the proposed change**, inspect the QA draft, enter a reviewer name and note, and click **Accept proposal**. | This records change approval. It does not execute tests or merge code. |
| 7 | Click **Run until review**. At **Approve the release proposal**, inspect the proposed canary, record a reviewer name and release note, and click **Accept proposal**. | Release approval is separate from change approval. The proposal remains simulated. |
| 8 | Click **Run until review** to finish. Open **Ticket history** and select this `TEST-…` run. | Inspect the original input, stage outputs, handoffs, and human decisions saved in PostgreSQL. Monitoring shares its result back with Broker-Triage. Times display in WIB. |

**Next step** advances one transition when narrating slowly. **Human reviews** lists actual waiting runs and uses the same review controls. **Decision trail** explains the selected ticket’s recorded decisions. **Stop run** records rejection and ends the run; it cannot be resumed.

### Optional revision

At the change checkpoint, enter a reviewer name and `Add a regression check for saved-card checkout failures and verify rollback triggers.` Click **Request changes**. Inspect the revised QA draft, use **Next step** to return to the checkpoint, and accept with a fresh note. The feedback loop revises local proposals; it does not execute CI. Ambiguous feedback can leave the run paused for clarification.

### Optional supporting views

**Meet the agents** explains Scout, Broker, Worker, and Security responsibilities and offers a signed Scout-Log migration against six configured nodes, using synthetic inputs and aggregate-only results. **Performance example** contains explicitly illustrative charts. **Experiment results** reads saved four-arm measurements: only seed 42, 100 tickets per approach. No cross-seed consistency or significance checks are run. Host timings are measured; deployment outcomes and DORA values are simulated.

Export dialogs show the selected scope and a file preview, with download and copy options. Clipboard exports have been verified; physical download completion was not verified in the in-app browser.

## Troubleshooting

- **Backend offline:** check Docker Desktop, Compose logs, and `/health`, then reload the dashboard.
- **Port 8000 occupied:** set `$env:ORCHESTRATOR_PORT = "8001"` before starting Compose and `$env:VITE_API_TARGET = "http://localhost:8001"` before starting Vite.
- **No history:** create and advance a ticket, then reopen Ticket history. Preserve the PostgreSQL volume.
- **Run unavailable after restarting the backend:** inspect persisted history and start a new run; active state is held in backend memory.
- **Stop services:** use Ctrl+C in the running terminals and `docker compose down`. Avoid `docker compose down -v` when retaining history and signing keys.

The demo shows structured agent communication with people deciding at impact, change, and release checkpoints, while clearly identifying prototype outputs.
