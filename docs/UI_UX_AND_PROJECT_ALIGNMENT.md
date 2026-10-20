# T2D-MAS: dashboard and project alignment

The report (§8.3, B.6) asks for five screens built on one principle: "one screen answers one
question", so that people never have to guess what the agents are doing. The dashboard keeps
that principle. It has eight views, each opening with one line on *what you see* and *why it
matters*, and adds animations that show the process instead of describing it. Technical names
such as performatives and JSON stay one click away.

## Report screens → dashboard views

| Report screen (§8.3) | Required elements | Dashboard view |
|---|---|---|
| 1 Pipeline overview | Nine-column board; ID, severity colour, current agent, time in stage, "waiting for a human" badge | **Tickets → Board**: nine columns with all of these. Severity, status and gates always show a word and an icon, not colour alone. |
| 2 Agent status | Role, static/mobile icon, status, load, migration path, bytes moved | **Agents**: family, static/mobile, live load and current tickets, and the five components. The **Investigate on the real nodes** trip animates the migration path with a byte counter (report T36). |
| 3 Decision trace | Per ticket: agent, input, output, confidence, τ and R_max, gate result, approver, expandable evidence | **Decision trace**: a seekable animated flow and a timeline, with each gate's values shown against its limits; JSON export. |
| 4 Approval inbox | Sorted by risk × waiting time; evidence; approve, or reject with a reason | **Human reviews**: sorted by severity risk × minutes waiting. Each gate shows value against limit. Approve / Request changes / Reject and stop, with a reason always required. The six-gate table is on the same page. |
| 5 Performance report | DORA and agent metrics, 30-day charts, Static/Mobile toggle, CSV export | **Monitoring**: telemetry playback with the SLO line, alert → follow-up ticket, the canary bar, and the illustrative DORA report with the Static/Mobile comparison and CSV. |
| (added) | Explain the system to a first-time viewer | **Overview**: an animated replay of the TCK-1042 flash-sale story and an idea-vs-prototype table. |
| (added) | Let a person try one ticket | **Run a ticket**: the natural-language feedback inbox, a live animated journey, each agent's five steps, and review at the gate. |
| (added) | Show what the evaluation measured | **Experiment results**: A0–A3 results (each metric marked measured, scored or simulated) and sample evaluation tickets. |

The other UI requirements from B.6 are covered too:
- server-sent events, so the timeline "feels alive";
- light and dark mode;
- three text sizes;
- colour is never the only signal.

## Animations

- **Pipeline flow** (Overview, Run a ticket, Decision trace). A ticket marker moves through the nine stages. Message envelopes travel between agents, labelled with what they mean ("Call for bids", "Bid", "Result shared"). Contract Net bids fan out and come back, and the winner is highlighted. Gate shields pulse while waiting for a person. A feedback-loop arc runs from monitoring back to triage.
- **Scout-Log trip** (Agents, and Run a ticket's investigation). Signed bundles go out to six nodes, and aggregates come back with live byte counts. The Static pull vs Mobile agent comparison uses the report's cost model.
- **Monitoring board** (Monitoring). An hour of telemetry plays back. The payment-db anomaly pulses, and its alert becomes a ticket that lands at feedback capture. The canary steps from 5% to 100%.

The player controls are play, pause, step, speed and a slider.

With *prefers-reduced-motion*:
- nothing starts by itself;
- moving parts show their end state;
- counters jump to their value;
- every step stays reachable.

Each animation also has a text version, and captions are read out per step.

## Live, simulated and replay

Every panel says where its data comes from:
- **Live:** the running backend.
- **Simulated by backend:** seeded simulators for CI, deploys and telemetry.
- **Replay · illustrative:** recorded example data.
- **Report model:** the cost model in report §5.4.3.
- **Recorded:** the saved audit log.

Without the backend, the dashboard switches to replay mode instead of failing.

## Boundaries the interface states

- **What is real and what is simulated:**
  - Triage, assignment, gates, the audit log, the node trips, signing and egress checks are real.
  - Planning, the draft PR, CI, deployment and telemetry are simulated.
- **No undo window:** the report's 30-second undo for autonomous actions is not implemented.
- **Local mode:** active runs live in memory; Docker mode keeps the audit history in PostgreSQL.
- **Unauthenticated reviewers:** a reviewer is a typed name, not a logged-in identity.

## Verification

- **Frontend:** 63 tests, including guards for one `fetch` site, no threshold literals and no dead CSS, plus the production build.
- **Backend:** 73 tests.
- **Live browser walk:** done by the dashboard session against a local-mode backend.
  - Every gate type, including the duplicate link and the secret-scan redraft.
  - The Scout-Log trip on the real nodes.
  - Alert → follow-up ticket, and the regression loop.
  - Saved runs, experiments, dark mode and a 375 px layout, with no console errors.

See `docs/AUDIT.md` for the comparison with the original idea.
