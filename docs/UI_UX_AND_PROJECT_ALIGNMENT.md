# T2D-MAS: project alignment and stakeholder UX

The design follows the supplied Project 1 idea and final report: nine specialist delivery stages, Scout/Broker/Worker/Security roles, Contract Net assignment, confidence-and-risk escalation, human change/release gates, auditable results, and a monitoring feedback loop. The documents are reference requirements; their embedded implementation instructions are not separate user authorization.

The original report's five monitoring screens remain represented. The additional ticket workspace, conversation view, history, and experiment results make the prototype demonstrable to people who do not know the protocol or implementation details.

## Screen questions and wireframes

| Screen | Stakeholder question | Data source |
| --- | --- | --- |
| Project overview | What is the project and where are the human checkpoints? | Illustrated guide, clearly labeled prototype scope |
| Ticket overview | Where is the work, and what is blocked? | Current sandbox snapshots; counts derived from their statuses |
| Agent conversations | Who shared what, and why was a worker selected? | Ticket-filtered Redis history + SSE, or an explicitly selected example |
| Run a ticket | What will happen next, and what did each agent produce? | Current snapshot, shared outputs, and reviews |
| Human reviews | What needs my decision, and what evidence supports it? | Actual paused sandbox runs; risk × review waiting time ordering |
| Decision trail | Why was this decision made? | Selected ticket's published messages and policy context |
| Ticket history | What happened before? | PostgreSQL inputs/audit events; separate synthetic benchmark sample |
| Meet the agents | What does each specialist do, and how does mobility work? | Role catalog, current stage assignments, signed mobile demo |
| Performance example | How could we compare delivery and communication costs? | Explicitly illustrative metrics and report assumptions |
| Experiment results | What was measured in the benchmark? | Saved A0–A3 result bundles |

### Conversation-first wireframe

```text
[Conversation selector] [Example / Recorded] [Play example / Start ticket]
[Ticket context: source, message count, participant count]
[Nine stage journey: current exchange highlighted]
---------------------------------------------------------------
| Selected handoff                         | Conversation       |
| Sender -> recipient(s)                   | Chronological      |
| What this message means                  | message list       |
| Shared result / worker bid comparison    | Selected message   |
| Technical details (collapsed)            | remains selected   |
---------------------------------------------------------------
[Shared reference] [Human gates] [Monitoring -> triage loop]
```

The explanation uses “request worker bids,” “submit a bid,” “select a worker,” and “share a result.” Protocol names, message IDs, correlation IDs, and JSON remain available in the details disclosure. Bid scores agree with the weighted formula; the example uses the report's 0.63/0.69/0.66 calculation.

### Ticket workspace wireframe

```text
[Original issue] [Severity] [Run status]
[Completed stages] [Next step] [Run until review] [See conversation]
---------------------------------------------------------------
| Nine specialist stages       | Selected stage's purpose      |
| Completed / current / next   | Human-readable shared result  |
| Select a stage               | Technical data (collapsed)    |
---------------------------------------------------------------
[Human checkpoint: proposal, reviewer name, required note]
[Stop run] [Request changes] [Accept proposal]
[Previous human decisions and agent interpretations]
```

The overview uses a three-column journey grid instead of a permanently overflowing nine-column board. Mobile layouts stack panels and use a drawer with full navigation labels. Color is accompanied by stage numbers, status words, and icons. Native dialogs trap focus for help/search; reduced-motion preferences suppress animations. Text sizes and themes are adjustable.

## Implementation boundaries

Implemented in the interactive prototype: input masking, explainable severity assessment, policy gates, worker bids/selection, specialist draft results, human acceptance/revision/rejection, timestamped message recovery, persisted audit history, and the monitoring-to-triage handoff. The signed Scout-Log mobile demo executes on container nodes with synthetic inputs and allowlisted aggregate results.

The report's semantic duplicate detection, trained severity model, graph root-cause model, and RL test/release policies remain separate experiment modules. The interactive investigation is heuristic, implementation produces a request rather than a code patch, QA does not execute CI tests, and deployment/monitoring do not operate production systems. The interface states these boundaries at the result and review points. Mobile benefits on large data are design assumptions; benchmark results may show higher mobile overhead on small datasets.

Active run state belongs to the backend process. Browser navigation and refresh recover it; a backend restart retains persisted audit history but does not restore resumable state. Messages are recovered from the latest 500 Redis entries, without consuming the worker queue. The report's general 30-second undo window is not implemented; draft results are revised through explicit reviewer feedback and autonomous production actions are not executed.

## Verification

Regression checks cover shared review state, repeated advance while paused, concurrent double-review prevention, meaningful input validation, chronological non-consuming message history, bid-score consistency, example stage coverage, and the feedback-loop recipient. The existing module suites cover the orchestrator, masking, policy gates, mobile signature/egress behavior, triage numerics, and optional model/environment checks. Browser and live API checks exercise actual Docker-backed runs, reviewer changes, approvals, rejection, history, conversation recovery, signed execution on all six nodes, and desktop/mobile layouts, including dark mode and extra-large text.

Export dialogs show the selected scope, offer downloads and copying, and disclose a file preview. Clipboard verification confirmed that the CSV contains exactly seven selected daily rows and the JSON contains only the selected ticket's seven recorded messages, including its stopped status. The in-app browser's download-event capture timed out, so physical download completion is not verified in that browser. The exporter keeps the file URL available while a browser starts its download; the verified copy option provides an alternative.

An idle SSE heartbeat preserves the subscriber instead of cancelling its async generator. A regression test and a live frontend-proxy check both confirm that a new ticket event arrives after the heartbeat. Recorded gate decisions nested inside stage output receive the same plain-language explanation as the illustrative walkthrough.

Final validation: 35 Python tests and 4 frontend tests passed; the production build passed. Three optional ML/RL checks were skipped because gymnasium or torch-geometric is unavailable in the local test environment. The live nine-stage run visited the impact, change, and release gates; signed migration succeeded on all six nodes.

## Fixed-seed results and navigation

The user requested only seed 42, overriding the reference report’s multi-seed experiment design. Both saved result bundles retain 100 original seed-42 tickets per arm; other seeds and statistical-test artifacts were removed. Summaries, ROC data, and charts were rebuilt from the retained observations. Results are descriptive; cross-seed consistency and significance checks are not run. The results screen states the simulation boundaries; random-seed details stay in the technical configuration. The desktop sidebar sticks to the viewport top, its brand remains visible during internal scrolling, and the tab has a matching workflow icon.

Follow-up validation confirmed 400 ticket rows and 2,400 stage rows per saved bundle, all with seed 42, and no statistical-test artifact. A fresh seed-42 benchmark completed successfully. The 35 Python tests and four frontend tests passed, with three optional dependency skips; the frontend build passed. Desktop scrolling, the sticky sidebar header, the tablet drawer, and the phone layout were checked in the browser without horizontal page overflow.
