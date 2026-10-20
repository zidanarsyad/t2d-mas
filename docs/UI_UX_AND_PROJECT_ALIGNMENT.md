# T2D-MAS: dashboard and project alignment

The report (§8.3, Lampiran B.6) asks for five screens built on one principle: "one screen answers
one question", so that people never have to guess what the agents are doing. The dashboard keeps
that principle. It has eight views. Each view opens with one line on *what you see* and one on
*why it matters*. Animations show the process instead of describing it, and technical names such
as performatives and raw JSON stay one click away.

## Report screens → dashboard views

| Report screen (§8.3) | Required elements | Dashboard view |
|---|---|---|
| 1 Pipeline Overview | Kanban with nine columns; card with ID, severity colour, current agent, time in stage, "waiting for a human" badge | **Tickets** (`#tickets`), **Board** tab: one column per stage, with its agent. Each card shows the ticket ID, severity, title, the agent or squad, and its time in the stage, or *Waiting for a human: [gate]* when it is blocked. Tiles above the board count the tickets in progress, waiting for a human, and finished, stopped or linked. A **Saved runs** tab (`#tickets/saved`) reads the latest 50 tickets back from the audit log. |
| 2 Agent Status | Role, static/mobile icon, host, status, load, heartbeat; migration path and bytes moved for mobile agents | **Agents** (`#agents`): the eleven agents (nine stage agents, Scout-Log and Security-Policy) with family, static or mobile, open tickets, and the five components of the latest real run. The Scout-Log trip animates the migration path with a byte counter (report T36). Not built: host, status and heartbeat per agent. |
| 3 Decision Trace | Per ticket: agent, input, output, confidence, τ and R_max, gate result, approver; rows open to show raw evidence | **Decision trace** (`#trace`): an animated flow and a timeline of the ticket's messages. Selecting a row jumps the flow to that step and shows the message, its output, the τ and R_max it ran under and, for the auction, the bid table. Human decisions show the reviewer and the quoted reason. **Export JSON** saves the raw trace. The full audit log, with every policy check against its limits and every merge or deploy, is under **Tickets → Saved runs**; the trace falls back to it when the messages are no longer loaded. |
| 4 Approval Inbox | Sorted by risk × waiting time; evidence; the agent's recommendation; Approve, or Reject with a reason | **Human reviews** (`#reviews`): sorted by severity risk × minutes waiting, with a severity filter. Each item shows the value against its limit and what the agent proposes. The choices are Approve, Request changes and Reject and stop; a reason is always required. The six-gate table is on the same page. |
| 5 Performance Report | DORA and agent metrics, 30-day line chart, CSV export | **Monitoring** (`#monitoring`): release-health playback with the SLO line, alert → follow-up ticket, and the canary bar. Below it are the DORA and agent metrics with a 30-day chart, CSV export and the Static pull vs mobile agent comparison; these numbers are an illustrative sample. |
| (added) | Explain the system to a first-time viewer | **Overview** (`#overview`): the animated TCK-1042 flash-sale replay, the nine stages in three phases, and an idea-vs-prototype table (real, mixed or simulated). |
| (added) | Let a person try one ticket | **Run a ticket** (`#run`): the feedback inbox in Indonesian and English, a start form with two demo options, the live animated journey, each agent's five components, and the review at each gate. |
| (added) | Show what the evaluation measured | **Experiment results** (`#experiments`): the saved A0–A3 runs, each number marked measured, scored or simulated, and a **Sample tickets** tab. |

### Old links

The first dashboard had ten views. Their links still work: the old hash is rewritten in place.

| Old hash | Opens |
|---|---|
| `#test` | `#run` |
| `#pipeline` | `#tickets` |
| `#history` | `#tickets/saved` |
| `#approvals` | `#reviews` |
| `#communications` | `#trace` |
| `#performance` | `#monitoring` |

`#overview`, `#trace`, `#agents` and `#experiments` kept their names.

### Other requirements from §8.3.6 and B.6

- **Live updates:** server-sent events (`GET /events`) drive the journey and the timeline, not polling.
- **Colour is never the only signal:** severity, gate and status always show an icon and a word.
- **Comfort:** light and dark mode, and three text sizes (Standard, Large, Extra large).
- **Finding a ticket:** Ctrl+K searches tickets; the bell counts the tickets waiting for a human.
- **Styling:** B.6 named Tailwind. The dashboard uses React, Recharts and one plain CSS file instead.
- **Not built:** the 30-second undo window for autonomous actions (see Boundaries).

## Animations

Three animations show the process. Each one is driven by a small step player: play or pause,
previous, next, restart, speed 0.5× / 1× / 2×, and a slider. Only the Overview replay starts by
itself, and players pause while the browser tab is hidden.

**Pipeline flow** (Overview, Run a ticket, Decision trace)
- A ticket marker moves through the nine stages. Each stage shows its state as a word: Done, Current, Waiting for a human, Revising, Upcoming, Skipped or Stopped.
- Message envelopes travel between agents along a faint trail with an arrow. Each envelope carries its message type (`inform`, `cfp`, `propose`, `accept-proposal`, `reject-proposal`). The caption under the flow says in plain words what happened.
- In the Contract Net auction, `cfp` envelopes fan out to the bidders: the three squads in a live run, three workers in the replay. The bids come back as chips with their utility, and the best one says *Winner*. Afterwards the flow keeps a label such as *Payments squad · 0.87*.
- Gate shields sit between the stages. A dashed shield ("if risky") stops only when its rule fails. A waiting gate turns amber and its ring pulses; a passed gate turns green, a stopped one red.
- Labels on the flow show the duplicate check ("New issue", "Duplicate of …"), the winning squad and the bytes Scout-Log moved.
- An arc runs from Monitoring back to Triage: the feedback loop.
- In a live run, frames come from the backend's messages as they arrive and play one after another.

**Scout-Log trip** (Agents, and the Investigation stage of Run a ticket)
- The orchestrator sits in the middle with a byte counter. The six data nodes form a ring around it.
- **Report model** for the flash-sale incident, six nodes × 1,365 MB:
  - Mobile agent: Sign → Dispatch → Run on the node → Return → Done. A *signed bundle* travels to each node and an *aggregate* travels back, while each node keeps a *1,365 MB stays here* chip. In total 84 MB moves in about 27 s.
  - Static pull: Pull raw logs → Done. Every node sends its 1,365 MB: 8,190 MB in about 10 min 55 s.
  - Tiles show the bytes saved, the speed-up, the break-even (14 MB per node) and the migrate rule (above 42 MB per node).
- **Live trip:** *Investigate on the real nodes* sends Scout-Log to the six data nodes. Each node shows a spinner until it answers, then turns green, and the counter adds its real bytes. Node-6 holds 30 MB, so its exporter answers instead.
- A text log lists every node: whether the agent ran there, the bytes moved and the raw logs that stayed.

**Monitoring board** (Monitoring)
- An hour of telemetry plays minute by minute, with the SLO line and the flash-sale period marked. Each service shows its value and *Within SLO* or *Breaks SLO*.
- At minute 20 the payment-db alert appears. *Open a follow-up ticket* sends a ticket along a small pipeline strip to Feedback capture and links to the board.
- The canary bar steps 5% → 25% → 50% → 100% at minutes 40, 46, 50 and 54. The 5% step is marked autonomous when the risk is at most 0.30; the 100% step needs a person.

## Where the data comes from

Every animated or numeric panel carries a source label:

| Label | Meaning |
|---|---|
| **Live** | Data from the running backend |
| **Simulated by backend** | The backend produced it with seeded simulators (plan, draft PR, CI, deploys, telemetry) |
| **Mixed: real + simulated** | The Investigation stage: real trips, signing and egress checks over simulated node logs |
| **Replay · illustrative** | Recorded example data in the dashboard, not a live run |
| **Report model** | Computed from the report's cost model (mobile agent vs static pull) |
| **Recorded** | Saved earlier and played back: the Decision trace flow, and the audit log when the live messages are gone |

Plain tags do the same job in a few places: **Live inbox** or **Offline sample** on the feedback
inbox, and **Illustrative sample** on the delivery report.

## Replay mode

The top-bar badge says **Live · local** (or **Live**, in Docker mode) while the backend answers.
Hovering over it shows the storage, bus, node and triage-model details. Without the backend the
badge says **Replay mode**, and every view still works:

| View | Without the backend |
|---|---|
| Overview | Plays the TCK-1042 replay (23 steps, about 26 s at 1×) |
| Run a ticket | Shows the offline inbox. Starting a run is disabled; **Watch a recorded run** plays the TCK-1042 replay with each stage's components |
| Tickets | Shows one illustrative card: TCK-1042 waiting for its release sign-off |
| Human reviews | Explains that reviews need the backend, and keeps the six-gate table with the dashboard's fallback policy |
| Decision trace | Plays the TCK-1042 example |
| Agents | Plays the report model; *Investigate on the real nodes* is hidden |
| Monitoring | Generates the same seeded hour in the browser; a follow-up ticket is simulated |
| Experiment results | Explains the four designs; saved results need the backend |

When the backend comes back, the dashboard reconnects by itself.

## Reduced motion and text versions

With *prefers-reduced-motion: reduce* set in the operating system:
- nothing starts by itself;
- CSS switches off every animation and transition, so each step shows its end state, and the trail arrow still shows who sent what;
- counters jump to their value;
- the telemetry chart shows the whole hour at once;
- live updates and live trip answers appear without waiting for the motion;
- every step stays reachable with the player buttons or the slider.

Each animation also has a text version:
- a caption per step, read out by screen readers when the player is paused;
- a hidden list of the stage states;
- the trip log per node;
- the anomaly and the canary steps as text.

## Boundaries the interface states

- **What is real and what is simulated:**
  - Triage, assignment, the gates, the audit log, the node trips, signing and egress checks are real.
  - Planning, the draft PR, CI, deployment and telemetry are simulated, and their stages say so.
- **No undo window:** the report's 30-second undo for autonomous actions is not built.
- **Local mode:** active runs live in memory. Docker mode keeps the audit history in PostgreSQL.
- **Unauthenticated reviewers:** a reviewer is a typed name, not a logged-in identity.

## Verification

On 20 October 2026:
- **Frontend:** `npm test` passes 63 tests. They include guards for one `fetch` site, no threshold literals in pages and no dead CSS.
- **Python:** `python -m pytest agents/tests triage/tests rca/tests envs/tests -q` passes 73 tests, 55 of them in `agents/tests`.
- **Browser walk** against a local-mode backend, following the live demo guide:
  - the FB-001 run with the impact gate, the auction, the trip, merge review and release sign-off;
  - the duplicate link (FB-002) and the duplicate review (FB-011, FB-012);
  - the secret-scan redraft and the shipped regression with its follow-up ticket;
  - Decision trace seeking and export, Saved runs, Investigate on the real nodes, the monitoring alert and Experiment results;
  - the old hashes, and every view in replay mode with the backend stopped.
- **Not seen in the browser:** the canary gate (the release risk stayed between 0.06 and 0.30 in 36 runs; the backend tests cover it) and reduced motion (the browser pane cannot emulate it; checked in the code).

See `docs/AUDIT.md` for the comparison with the original idea, and `frontend/README.md` for the
code layout.
