# Agent catalog

This catalog maps the project's intended agents to their task, objective, capabilities, and current implementation status. The role split follows the project idea and report; the status column describes this repository today.

## Agent roles

| Agent | Task and objective | Capabilities and expected output | Current implementation |
|---|---|---|---|
| **Scout-Feedback** | Accept a report and normalize it into a consistent ticket. | Validate and normalize fields; produce a ticket record with source and intake time. | Manual sandbox trims text, masks common email/phone/token patterns, and records an intake event. No external tracker connector is configured. |
| **Broker-Triage** | Classify the ticket and identify related work so the right response can be selected. | Rule/model severity score, category, duplicate candidates, evidence, and escalation decision. | Rule-based severity classification is active in the sandbox. Its score is a heuristic, not a calibrated probability. Duplicate search is not wired into that path. |
| **Broker-Assign** | Match work to a capable, available worker. | Contract Net CFP, proposals, utility comparison, and award/reject messages. | The manual ticket sandbox runs a deterministic Contract Net round with three local worker profiles. CFP, bids, award/reject routes, and winner utility are written to the audit history and live message stream. |
| **Scout-Log** | Collect local runtime evidence while limiting data movement. | Filter and aggregate logs/metrics; return allowlisted evidence, with optional signed mobile execution. | Signed mobile bundle execution and egress checks are implemented. This is a separate demo route, not a stage in the manual sandbox. |
| **Worker-Investigate** | Rank likely causes using ticket context and evidence. | Root-cause hypotheses with evidence and confidence. | The sandbox emits low-confidence, keyword-based hypotheses from ticket text and says when telemetry was not collected. The graph RCA model in `rca/` remains a separate experiment. |
| **Worker-Plan** | Turn investigation results into a safe, reviewable work plan. | Ordered subtasks, acceptance criteria, and effort estimate. | The sandbox emits a deterministic plan template and states when effort cannot be estimated without repository or sprint data. |
| **Worker-Impl** | Prepare a proposed code change for a scoped task. | Repository-grounded patch or draft change for review. | The sandbox records a draft request only. It does not generate or edit code because no repository coding tool or model is connected. |
| **Worker-QA** | Check a proposed change against its acceptance criteria. | Prioritized tests, test report, regressions, and pass/fail recommendation. | The sandbox emits a QA checklist and marks the result undetermined when no patch or CI runner exists. QA and RL evaluation components under `envs/` remain separate experiments. |
| **Worker-Deploy** | Roll out an approved change safely and recover on failure. | Risk-scored canary, telemetry check, deployment recommendation, and rollback. | The sandbox records a 5% canary proposal only. It never deploys; a human release checkpoint remains in the orchestrator. |
| **Scout-Monitor** | Watch service health after release and feed incidents back into intake. | SLO/anomaly signals and follow-up ticket. | The sandbox marks telemetry as unavailable and identifies the triage feedback-loop target; no production monitoring connector is configured. |
| **Security-Policy** | Enforce policy and audit all gated or irreversible work. | Confidence/risk gate, secret and egress checks, approval requirement, append-only audit. | The deterministic gate, signed-bundle checks, and append-only Postgres audit are implemented. Full policy enforcement across every specialist stage is not integrated. |

## Shared agent contract

`agents/base.py` defines the intended agent loop: perceive input, remember relevant state, reason about a proposal, act behind a policy gate, and report an auditable result. `agents/orchestrator.py` models the nine stages from intake through monitoring. The manual sandbox records a result for every stage, sends stage handoffs as timestamped ACL messages, and exposes the Contract Net negotiation in the live communication view. Results are explicitly bounded: investigation is heuristic, planning is templated, implementation is a draft request, QA is a checklist, and release/monitoring are simulations without external tools.

## Human review behavior

- Accept clears the current pause and advances one stage.
- Reject records the reviewer and note, then stops the run.
- Reviewers can accept, reject, or request changes. Request changes sends the note to the stage agent, interprets it as requested changes, constraints, and evidence (with clarification when ambiguous), reruns that stage, and records the revised proposal. Triage uses OpenRouter when configured; QA incorporates requested checks, while deployment remains a proposal-only simulation.
- Accepted notes are interpreted as context for the next stage and included in its ACL handoff.
- Merge and full-release checkpoints remain human-gated. A rejected run must be corrected and submitted again by a person.

## LLM use

The interactive sandbox uses OpenRouter optionally for Broker-Triage and for structuring reviewer feedback. The repeatable evaluation harness remains deterministic. LLM interpretation is a proposal: reviewer decisions, policy gates, audit, signature checks, and irreversible-action approvals remain outside the model.

## Project boundary

The repository is a teaching prototype, not an autonomous production delivery system. Its interactive sandbox now traces the nine stages, Contract Net negotiation, audit outputs, and human gates end to end, but it does not connect real repository editing, CI, production deployment, or telemetry. The machine-learning, graph, and RL experiments under `triage/`, `rca/`, and `envs/` are not all composed into the sandbox workflow.
