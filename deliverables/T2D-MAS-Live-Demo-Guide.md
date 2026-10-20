# T2D-MAS live demo guide

This script follows real-style user complaints from the feedback inbox to a monitored release.
The audience sees:
- the agents handing work to each other;
- the Contract Net auction;
- the mobile agent's trip to the data nodes;
- the six human gates;
- the feedback loop from monitoring back to triage.

Parts 1 and 2 are the core. The other parts can be shortened or skipped.

Planning, implementation, QA, deployment and monitoring use seeded simulators. Every panel says
whether its data is live, simulated or illustrative. No real repository, CI, cluster or telemetry
is connected.

## Before you start

Start the backend and the dashboard in local mode (no Docker). Use two terminals in the
repository root:

```powershell
python -m uvicorn agents.app:app --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

In the Claude desktop app, `.claude/launch.json` starts both (`backend` and `dashboard`).
Open `http://localhost:5173`.

Check these before the audience arrives:
- The top bar says **Live · local**. Hover over it: memory storage, memory bus, in-process nodes, local rules for triage.
- `OPENROUTER_API_KEY` is not set. Triage then uses its local rules, so the demo repeats.
- The board is empty. Local mode keeps everything in memory, so restart the backend before the demo. A message that already ran once comes back as a duplicate.
- No Docker stack of this project is running (`docker ps`). Its orchestrator also uses port 8000 (see Troubleshooting).

Good to know:
- At every gate the name field says *Project reviewer*. Type your own name. A reason is always required.
- The simulators are seeded from the ticket id, and every run gets a new id. Test counts, NAPFD and the release risk therefore change a little from run to run.

To use the full Docker stack instead (Redis, PostgreSQL, six node containers), run
`docker compose up --build`. After a database schema change, run `docker compose down -v` once.

## Part 1: Overview, the flash-sale story

This part also works with the backend stopped.

**Do**
1. Open **Overview**. The TCK-1042 replay starts by itself.
2. Use the player to pause, step back or forward, change the speed or drag the slider.

**Say**
- 2,143 crash reports arrive in four minutes. Scout-Feedback turns them into one ticket.
- Triage rates it Critical. Critical always carries risk 1.00, above R_max 0.60, so a person confirms.
- In the Contract Net auction three workers bid. Worker-Investigate wins with utility 0.69.
- Scout-Log moves 84 MB in about 27 s. The 8,190 MB of raw logs stay on the nodes.
- Merge and full release wait for a person. Monitoring sees no SLO breach, and the loop returns to Triage.
- The *Idea vs prototype* table further down says which parts of this prototype are real, mixed or simulated.

## Part 2: Run a ticket, one crash report end to end

### Start the ticket

**Do**
1. Open **Run a ticket**. The inbox is labelled **Live inbox**.
2. Select **Flash-sale burst**.
3. Select the **Crash reporter** message from 20:06 WIB: "Aplikasi langsung nutup sendiri pas aku pencet Bayar di flash sale jam 20.03, saldo GoPay kepotong…". The form now says *From Crash reporter · FB-001*.
4. Leave both demo options unticked. Select **Start this ticket**.

The app-store review from 20:05 WIB says almost the same thing. That one is FB-002; keep it for
Part 3.

**Say**
- This is real user language: casual Indonesian slang with an emoji.
- Scout-Feedback has already read it. Open its stage: language Bahasa Indonesia, component payment (cue words bayar, gopay, saldo), app 4.18.2 on Android, a derived title.
- It also checked for personal data. This message has none; an e-mail or phone number would be masked.

### The first gate: confirm the impact assessment

**Do**
1. Select **Run until a human is needed**.
2. The run stops at **Waiting for a human: Confirm the impact assessment**. The bell and **Human reviews** now show 1.

**Say**
- Triage found no earlier ticket and rated this one Critical: the balance was deducted, but there is no order.
- This is the autonomy gate. Confidence 0.84 passes (at least τ 0.70). Risk 1.00 fails (at most R_max 0.60). Both rules must pass for the agent to continue alone.
- The **Triage** stage below shows the agent's five steps: perceive, remember, reason, act, report. Every agent works this way.

**Do**
3. Type your name and a reason, then select **Approve**. The page says *Approved and recorded. Next: Assignment.*

### The auction, the trip and the draft change

**Do**
1. Select **Run until a human is needed** again and watch the journey panel. (**Next step** plays one stage at a time, if you want to slow down.)
2. When the run stops, select the **Assignment**, **Investigation**, **Planning**, **Implementation** and **QA** stages one by one.

**Say**
- **Assignment:** `cfp` envelopes fly to three squads: Payments, Mobile app and Platform. Their bids come back, and Payments wins on skill and low workload. Its SLA is 2 hours.
- **Investigation:** Scout-Log visits all six data nodes. The trip panel under the stage shows each node.
  - Nodes 1–5 hold 1,365 MB of logs each, so the signed analysis code runs there.
  - Node-6 holds only 30 MB, below the 42 MB rule, so its own exporter answers.
  - About 12 KB moves; 6,855 MB of raw logs stay on the nodes. The ranking puts payment-db first.
- **Planning:** four subtasks with estimates, three Given/When/Then criteria and a sprint-capacity check.
- **Implementation:** a simulated draft PR. Security-Policy's secret scan passes.
- **QA:** about 100 of 3,400 tests that fit an 8-minute budget, riskiest first. NAPFD scores how early the failing tests ran (1.0 = first).

### The merge review

The run has stopped at **Review the proposed change**. The evidence shows the tests selected
within 8 minutes, 0 failed tests, and the test-order quality (NAPFD) for information.

**Say**
- Merging is irreversible, so a person always reviews it.

**Do**
1. Type your name and a reason, then select **Approve**.
2. Under *Human decisions and actions*: *Merge: executed with [your name]'s recorded approval*. The merge runs only now.

### Release and monitoring

**Do**
1. Select **Run until a human is needed**.

**Say**
- Deployment scores the release risk from the change size, test failures, a critical-service flag and the service's rollback history.
- At 0.30 or less, the 5% canary starts by itself. This is the usual case; this ticket usually scores about 0.25.
- Above 0.30 the run first stops at **Approve the 5% canary**. The score changes with each run, so this gate shows up only now and then.
- The run now stops at **Approve the full release**: the canary passed, and the risk score is shown for information. A full release is irreversible, so it always needs a person.

**Do**
2. Type your name and a reason, then select **Approve**.
3. Select **Run until a human is needed** once more.

**Say**
- Monitoring watches payment-db for 30 simulated minutes against its SLO: *Release healthy for 30 minutes; baseline updated and ticket closed.*
- The page says *Prototype run finished*, and the decisions panel lists both irreversible actions with the approver's name.

## Part 3: Duplicates and the review queue

### Linked automatically (FB-002)

**Do**
1. Select **New ticket**, then **Flash-sale burst**.
2. Select the **App store review** from 20:05 WIB (rinaaa_s, 1/5 stars). It repeats the FB-001 complaint.
3. **Start this ticket**, then **Run until a human is needed**.

**Say**
- *Linked as a duplicate of TEST-…. This run is closed.* The similarity is about 0.96, at least 0.85, so triage links it and the later stages are skipped.

### A person decides (FB-011, then FB-012)

**Do**
1. Select **New ticket**, then **Show other messages** once.
2. Select the **App store review** "OTP gak masuk2 dari tadi, gabisa login sama sekali…" (FB-011). Start it and run it. It stops at the impact gate: High, with confidence 0.68 below τ. Leave it waiting.
3. Select **New ticket**. The inbox is back on its first set.
4. Select the **Customer-service chat** "kak kode OTP nya gak masuk2…" (FB-012). Start it and run it.
5. It stops at **Confirm the duplicate**: similarity to the FB-011 ticket is about 0.71.

**Say**
- At 0.85 or more triage links a duplicate by itself. Below 0.70 it opens a new ticket. In between, a person decides.

**Do**
6. Open **Human reviews**. Both OTP tickets wait there. Select the *Confirm the duplicate* item.
7. Type a reason and select **Approve** to link it and close the run. (**Request changes** would treat it as a new ticket.)

**Say**
- The queue is sorted by severity risk × minutes waiting, and you can filter it by severity.
- Each item shows the value against its limit, the agent's proposal and its five steps.
- The six-gate table below says when the agent continues alone, when a person decides, and which decisions cannot be undone.

## Part 4: The two demo options

Both options are checkboxes on the start form. Pick a message that has not run yet, or it is
linked as a duplicate.

### The secret scan

**Do**
1. **New ticket**. Select the **App store review** "Pencarian lemot bgt skrg, ketik 'sepatu'…" (FB-041).
2. Tick **Put a test secret in the draft change**. Start it and run it.
3. The run stops at **Remove a secret from the change**: 1 secret found, limit 0. **Approve** stays disabled.
4. Type a reason and select **Request changes**.

**Say**
- A change with a secret can only be redrafted or stopped, never approved.
- After the request, Worker-Impl redrafts the change without the key, and the new draft passes the scan. Run on to the merge review if you like.

### The shipped regression

**Do**
1. **New ticket**. Select the **App store review** "voucher gratis ongkir gak bisa dipake…" (FB-051).
2. Tick **Ship a regression**. Start it and run it. Approve the merge, run again, approve the full release, and run once more.

**Say**
- Monitoring sees the regression after the full release: *Release unhealthy … opening a follow-up ticket.* The canary runs without the regression, so only monitoring can catch it.
- *Human decisions and actions* links the follow-up ticket.

**Do**
3. Open **Tickets**. The follow-up waits in the **Feedback capture** column as "Regression after TEST-…".

**Say**
- This is the feedback loop: a problem after a release becomes new work at the start of the pipeline.
- The board shows every ticket's stage, severity, agent, time in stage and whether it waits for a person.

## Part 5: Decision trace, why it happened

**Do**
1. Open **Decision trace** and select the FB-001 ticket. The list shows the newest first, so it is the lower of the two "Aplikasi langsung nutup…" entries.
2. Select a timeline row, for example *Call for bids* or *Bid accepted*. The flow jumps to that step, and the detail panel shows the message (with the bid table for the auction).
3. Select a *Human decision* row: it shows the reviewer's name and the quoted reason.
4. Use the player, or select **Export JSON**.
5. Open **Tickets**, then **Saved runs**, and select the same ticket.

**Say**
- The trace replays the agents' messages. Each message carries the τ and R_max it ran under.
- Saved runs shows the full append-only audit log. Every policy check has its values against the limits, for example *Confidence 0.84 vs τ 0.70; risk 1.00 vs R_max 0.60*.
- The merge and the full deploy each appear twice: *authorized to execute*, then *executed*.

## Part 6: Agents, the mobile agent

**Do**
1. Open **Agents**. Select an agent to see its five steps from its latest real run.
2. Under *The mobile agent at work*, select **Investigate on the real nodes**.
3. Switch between **Static pull** and **Mobile agent**.

**Say**
- The live trip is labelled **Live**. It shows the real bytes per node, and node-6 again answers through its exporter.
- The switch plays the report's cost model for the flash-sale incident: a static pull moves 8,190 MB in about 10 min 55 s; the mobile agent moves 84 MB in about 27 s.
- Moving the agent pays off above 14 MB per node (the break-even). The rule ships it only above 42 MB, which is why node-6 (30 MB) uses its exporter.

## Part 7: Monitoring and the feedback loop

**Do**
1. Open **Monitoring**. Keep the scenario **Flash sale (incident)** and select **Play** (2× is fine).
2. At minute 20 an alert appears. Select **Open a follow-up ticket**.

**Say**
- The data is labelled **Simulated by backend**. payment-db breaks its SLO at minute 20: p95 latency 2,348 ms against a baseline of 310 ms.
- The alert becomes a new ticket that enters at Feedback capture: *TEST-… created → Feedback capture → Triage.* It appears on the **Tickets** board.
- The canary bar shows 5% → 25% → 50% → 100%. The 5% step starts alone only when the risk is at most 0.30; the 100% step needs a person.
- The delivery report below (DORA metrics, CSV) is an illustrative sample, not measured by this prototype.

## Part 8: Experiment results

**Do**
1. Open **Experiment results**.
2. Under *Saved run*, choose **30 Sep 2026**. That is the run the report cites. The 20 Oct run is a re-run with the same scores and different timings.

**Say**
- A0–A3 are four designs, run on the same 5 seeds × 100 synthetic tickets.
- Each number is marked measured, scored or simulated.
- The caveat: the synthetic tickets contain their severity word, so severity accuracy is 1.00 for every design. The **Sample tickets** tab shows it, and `docs/AUDIT.md` explains it.

## Local mode: changing the triage decision

Without `OPENROUTER_API_KEY`, the agent cannot interpret a free-text change request. A change
request at an impact gate therefore needs an explicit correction. FB-011's gate from Part 3 is a
good place to show it.

- **A vague note** ("Please look at this again"): the agent asks for a clearer note. Its question appears above the review form, and the history records *clarification requested*.
- **An explicit note** ("Users cannot log in at all; severity should be High"): *The agent revised its triage result.* Triage re-runs with your severity.
- On the next run the gate checks the revised result again. FB-011 keeps confidence 0.68, so it stops again, and you approve it.
- **Reject and stop** ends a run for good. Start a new ticket to try again.

## Troubleshooting

- **The badge says Replay mode.** The backend is not reachable. Start it; the dashboard reconnects by itself. Overview, Decision trace, Agents and Monitoring keep playing their recorded or simulated versions meanwhile.
- **"The backend is not reachable" now and then, while the badge says Live.** Another server answers on port 8000 for a few seconds. A typical cause is this project's Docker stack, whose orchestrator keeps restarting (for example because its Redis container is not running). Stop it with `docker compose down`, or set `$env:VITE_API_TARGET = "http://127.0.0.1:8000"` before `npm run dev`. Then select the button again.
- **Port 8000 is busy.** Start the backend on another port, for example `--port 8010`, and set `$env:VITE_API_TARGET = "http://127.0.0.1:8010"` before `npm run dev`.
- **A message goes straight to "Linked as a duplicate".** It already ran on this backend. Restart the backend for a clean board, or pick another message.
- **The Decision trace shows only a timeline, labelled Recorded.** The dashboard loads the last 500 agent messages. For older tickets the trace falls back to the saved audit log, without the animation. Pick a recent ticket.
- **The board is empty after a restart.** This is expected in local mode, because everything is in memory. Docker mode keeps the audit history in PostgreSQL.
- **Stopping.** Press Ctrl+C in both terminals. With Docker, use `docker compose down`, and add `-v` only if you also want to drop the database and the signing keys.
