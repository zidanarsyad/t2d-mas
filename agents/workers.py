"""Worker agents: they do the engineering work, from investigation to release.

Only investigation touches live infrastructure (the data nodes). Planning,
implementation, QA and deployment use the simulated tools in agents/tools.py,
because the prototype has no real repository, CI runner or production cluster;
their outputs say so in `simulation_note`.
"""
from __future__ import annotations

from typing import Any

from agents import tools
from agents.policy import canary_autonomous
from agents.scouts import ScoutLog
from agents.security_policy import SECRET_PATTERNS, find_secrets
from agents.stage_agent import StageAgent, StageContext, Step, decision
from eval.metrics import napfd
from rca.numerics import reference_mean_sage_scores

SIMULATED = "Simulated with seeded tools: no real repository, CI runner or cluster is connected."
EXPECTED_OUTCOME = {
    "payment": "the payment completes once and the order appears in the order history",
    "promo": "the voucher is accepted and the discount is applied once",
    "login": "the OTP arrives within 30 seconds and the user is signed in",
    "account": "the change is saved and shown after reopening the page",
    "search": "results appear within 2 seconds",
    "delivery": "the tracking status matches the courier's latest scan",
    "notification": "exactly one notification arrives",
    "app": "the app stays open and responsive",
    "other": "the reported problem no longer occurs",
}


def _top_suspect(ctx: StageContext) -> str:
    return ctx.outputs.get("investigation", {}).get("rca", {}).get("top_suspect") or \
        tools.COMPONENT_FAULT.get(ctx.ticket.get("component", "other"), "order-service")


class WorkerInvestigate(StageAgent):
    stage, family, execution_mode = "investigation", "Worker", "mixed"
    simulation_note = "Node logs are simulated, but the trip to each node, the signing and the egress checks are real."

    def identity(self, ctx: StageContext) -> str:
        return ctx.outputs.get("assignment", {}).get("winner", "Worker-Investigate")

    async def perceive(self, ctx: StageContext) -> Step:
        component = ctx.ticket.get("component", "other")
        return Step(component, f"Took over a {ctx.ticket.get('severity')} {component} ticket from Broker-Assign.")

    async def remember(self, ctx: StageContext, seen: Step) -> Step:
        chain = tools.COMPONENT_CHAINS.get(seen.data, tools.COMPONENT_CHAINS["other"])
        baselines = ctx.deps.repository.slo_baselines() or tools.DEFAULT_SLO_BASELINES
        return Step({"chain": chain, "baselines": baselines},
                    f"A {seen.data} request travels {' → '.join(chain)}; loaded their SLO baselines.")

    async def reason(self, ctx: StageContext, seen: Step, memory: Step) -> Step:
        threshold = (ctx.policy.agent_bundle_mb + ctx.policy.result_mb) * ctx.policy.migration_factor
        return Step(threshold, f"Plan: send Scout-Log to all {len(ctx.deps.nodes)} data nodes; ship the analysis "
                               f"code where a node holds more than {threshold:.0f} MB of logs, otherwise use the "
                               f"node's exporter; then rank the services on the call chain.")

    async def act(self, ctx: StageContext, seen: Step, memory: Step, plan: Step) -> Step:
        scout = ScoutLog()
        visits = [await scout.visit(ctx, node, seen.data) for node in ctx.deps.nodes]
        ctx.use_tool("scout_log.visit_nodes", simulated=False,
                     detail=f"{sum(v['mode'] == 'mobile_agent' for v in visits)} signed bundles, "
                            f"{sum(v['mode'] == 'node_exporter' for v in visits)} exporter calls")
        by_service = {visit["service"]: visit["aggregate"] for visit in visits if visit["aggregate"]}
        chain = [service for service in memory.data["chain"] if service in by_service]
        features = {}
        for service in chain:
            base = memory.data["baselines"][service]
            aggregate = by_service[service]
            features[service] = [tools.z_score(aggregate["latency_p95_ms"], base["latency_p95_ms"]["mean"],
                                               base["latency_p95_ms"]["std"]),
                                 tools.z_score(aggregate["error_rate"], base["error_rate"]["mean"],
                                               base["error_rate"]["std"])]
        ranking = []
        if chain:
            ctx.use_tool("rca.graphsage_mean", simulated=False, detail="rca/numerics.py, the report's example model")
            # One GraphSAGE-mean pass over the call chain (report section 6.6): a service's
            # score mixes its own anomaly with its neighbours', so the source of a cascade ranks first.
            scores = reference_mean_sage_scores([features[service] for service in chain],
                                                [(index, index + 1) for index in range(len(chain) - 1)],
                                                [[0.5, 0.0], [0.0, 0.5]], [0.6, 0.4])
            ranking = sorted(({"service": service, "score": round(score, 3)} for service, score in zip(chain, scores)),
                             key=lambda item: -item["score"])
        note = (f"Scout-Log visited {len(visits)} nodes; top suspect {ranking[0]['service']} "
                f"(score {ranking[0]['score']})." if ranking else "Not enough node evidence to rank services.")
        return Step({"visits": visits, "features": features, "ranking": ranking, "by_service": by_service}, note)

    def report(self, ctx, seen, memory, plan, result) -> dict[str, Any]:
        visits, ranking = result.data["visits"], result.data["ranking"]
        top = ranking[0]["service"] if ranking else None
        evidence = result.data["by_service"].get(top) if top else None
        intake = ctx.outputs.get("intake", {})
        steps = list(intake.get("reproduction_hints") or [])[:2] or [ctx.ticket["title"]]
        steps.append(f"Check {top} p95 latency and error rate during the same window" if top
                     else "Collect logs from the affected service")
        hypothesis = (f"{top} is the most likely cause: p95 {evidence['latency_p95_ms']} ms and "
                      f"{evidence['error_rate']:.1%} errors, versus a baseline of "
                      f"{tools.DEFAULT_SLO_BASELINES[top]['latency_p95_ms']['mean']} ms." if evidence
                      else "No hypothesis: the nodes on this call chain did not answer.")
        return {"investigator": self.identity(ctx), "mobile_agent": ScoutLog.agent_id, "window_minutes": 30,
                "node_visits": visits,
                "bytes_moved": sum(visit["bytes_sent"] + visit["bytes_returned"] for visit in visits),
                "raw_log_bytes_kept_on_nodes": sum(visit["log_bytes_kept"] for visit in visits),
                "raw_data_left_nodes": False,
                "rca": {"method": "GraphSAGE-mean reference pass over the call chain (features: latency z, error z)",
                        "features": result.data["features"], "ranking": ranking, "top_suspect": top},
                "hypothesis": hypothesis, "reproduction_steps": steps, "root_cause_confirmed": False,
                "summary": f"Ranked {top} as the top suspect after visiting {len(visits)} nodes." if top
                           else "Could not rank a suspect service."}


class WorkerPlan(StageAgent):
    stage, agent_id, family = "planning", "Worker-Plan", "Worker"
    simulation_note = SIMULATED

    async def perceive(self, ctx: StageContext) -> Step:
        service = _top_suspect(ctx)
        return Step(service, f"Read the investigation: fix {service}; {ctx.outputs.get('investigation', {}).get('hypothesis', '')}")

    async def remember(self, ctx: StageContext, seen: Step) -> Step:
        ctx.use_tool("project_board.capacity", simulated=True, detail="sprint board")
        board = tools.project_board(ctx.seed)
        return Step(board, f"{board['sprint']} has {board['capacity_hours_left']} hours of capacity left.")

    async def reason(self, ctx: StageContext, seen: Step, memory: Step) -> Step:
        service, severity = seen.data, ctx.ticket.get("severity", "Medium")
        scale = {"Critical": 1.5, "High": 1.2, "Medium": 1.0, "Low": 0.6}.get(severity, 1.0)
        intake = ctx.outputs.get("intake", {})
        platform = intake.get("platform") or "the affected platform"
        subtasks = [
            {"id": "S1", "title": f"Reproduce on {platform} (app {intake.get('app_version') or 'current'})", "hours": 2},
            {"id": "S2", "title": f"Fix {service}: {tools.FIX_IDEAS[service]}", "hours": 6},
            {"id": "S3", "title": "Add a regression test for the reported scenario", "hours": 2},
        ]
        if severity in {"Critical", "High"}:
            subtasks.append({"id": "S4", "title": "Prepare the rollback plan and a customer update", "hours": 1})
        for task in subtasks:
            task["estimate_hours"] = round(task.pop("hours") * scale, 1)
            task["owner"] = ctx.outputs.get("assignment", {}).get("squad", "assigned squad")
        when = (intake.get("reproduction_hints") or [ctx.ticket["title"]])[0]
        slo = tools.DEFAULT_SLO_BASELINES[service]["latency_p95_ms"]["slo"]
        criteria = [
            {"given": f"a customer on {platform}", "when": when,
             "then": EXPECTED_OUTCOME.get(ctx.ticket.get("component", "other"), EXPECTED_OUTCOME["other"])},
            {"given": "the fix is on the canary", "when": "real traffic reaches it",
             "then": f"{service} p95 latency stays under {slo} ms"},
            {"given": "the full regression suite", "when": "it runs", "then": "no previously passing test fails"},
        ]
        return Step({"subtasks": subtasks, "criteria": criteria},
                    f"Split the fix into {len(subtasks)} subtasks with Given/When/Then acceptance criteria.")

    def report(self, ctx, seen, memory, plan, result) -> dict[str, Any]:
        hours = round(sum(task["estimate_hours"] for task in plan.data["subtasks"]), 1)
        return {"subtasks": plan.data["subtasks"], "acceptance_criteria": plan.data["criteria"],
                "effort": {"hours": hours, "story_points": max(1, round(hours / 3)),
                           "method": "sum of subtask estimates, scaled by severity"},
                "sprint": {**memory.data, "fits_current_sprint": hours <= memory.data["capacity_hours_left"]},
                "summary": f"{len(plan.data['subtasks'])} subtasks, about {hours} hours; "
                           f"{'fits' if hours <= memory.data['capacity_hours_left'] else 'does not fit'} this sprint."}


class WorkerImpl(StageAgent):
    stage, agent_id, family, mobility = "implementation", "Worker-Impl", "Worker", "MOBILE"
    simulation_note = SIMULATED

    async def perceive(self, ctx: StageContext) -> Step:
        service = _top_suspect(ctx)
        return Step(service, f"Read the plan: change {service} and add regression tests.")

    async def remember(self, ctx: StageContext, seen: Step) -> Step:
        ctx.use_tool("repository.context", simulated=True, detail=seen.data)
        context = tools.repository_context(seen.data)
        return Step(context, f"Looked up the files that implement {seen.data}: {', '.join(context['files'])}.")

    async def reason(self, ctx: StageContext, seen: Step, memory: Step) -> Step:
        return Step(tools.FIX_IDEAS[seen.data], f"Approach: {tools.FIX_IDEAS[seen.data]}.")

    async def act(self, ctx: StageContext, seen: Step, memory: Step, plan: Step) -> Step:
        inject = bool(ctx.ticket.get("options", {}).get("inject_test_secret"))
        ctx.use_tool("repository.draft_diff", simulated=True, detail="draft branch, nothing is pushed")
        diff = tools.draft_diff(seen.data, ctx.ticket["ticket_id"], inject_secret=inject)
        ctx.use_tool("security_policy.secret_scan", simulated=False, detail="secret patterns on the diff")
        findings = find_secrets(diff["diff_text"])
        change_id = f"CHG-{ctx.ticket['ticket_id']}-r{ctx.revision}"
        if not findings:  # a draft that leaks a secret is never stored
            ctx.deps.repository.save_code_change({
                "change_id": change_id, "ticket_id": ctx.ticket["ticket_id"],
                "repository": memory.data["repository"], "branch_name": diff["branch"], "title": diff["title"],
                "diff_summary": diff["summary"], "files": diff["files_touched"], "tests_added": diff["tests_added"],
                "additions": diff["additions"], "deletions": diff["deletions"]})
        note = ("Drafted the change; Security-Policy found no secrets and the draft was recorded (not merged)."
                if not findings else "Drafted the change, but Security-Policy found a secret in it: blocked.")
        return Step({"diff": diff, "findings": findings, "change_id": change_id}, note)

    def report(self, ctx, seen, memory, plan, result) -> dict[str, Any]:
        diff, findings = result.data["diff"], result.data["findings"]
        preview = diff["diff_text"]
        for pattern in SECRET_PATTERNS:  # never show a secret, even in the review evidence
            preview = pattern.sub("<REDACTED SECRET>", preview)
        passed = not findings
        return {"draft_pr": {"change_id": result.data["change_id"], "branch": diff["branch"], "title": diff["title"],
                             "summary": diff["summary"], "files_touched": diff["files_touched"],
                             "tests_added": diff["tests_added"],
                             "diff_stats": {"files": len(diff["files_touched"]), "additions": diff["additions"],
                                            "deletions": diff["deletions"]},
                             "diff_preview": preview},
                "security_precheck": {"scanner": "Security-Policy secret patterns", "passed": passed,
                                      "findings": findings},
                "code_change_recorded": passed, "merged": False, "repository_modified": False,
                "decisions": [decision("secret_scan", passed, "no_secret_found" if passed else "secret_found",
                                       ctx.policy, findings=len(findings))],
                "summary": f"Draft PR on {diff['branch']} (+{diff['additions']}/-{diff['deletions']}); "
                           + ("secret scan passed." if passed else "blocked: a secret was found.")}


class WorkerQA(StageAgent):
    stage, agent_id, family = "qa", "Worker-QA", "Worker"
    simulation_note = SIMULATED

    async def perceive(self, ctx: StageContext) -> Step:
        draft = ctx.outputs.get("implementation", {}).get("draft_pr", {})
        return Step(_top_suspect(ctx), f"Received draft PR {draft.get('change_id')} touching "
                                       f"{', '.join(draft.get('files_touched', []))}.")

    async def remember(self, ctx: StageContext, seen: Step) -> Step:
        ctx.use_tool("ci.test_catalog", simulated=True, detail="3,400 tests with history")
        catalog = tools.test_catalog(seen.data, ctx.seed)
        return Step(catalog, f"The suite has {len(catalog):,} tests; loaded each test's failure history.")

    async def reason(self, ctx: StageContext, seen: Step, memory: Step) -> Step:
        # Risk-aware ordering (the report's RL policy is trained offline in envs/; this is
        # the hand-written baseline it is compared against): history 50%, closeness 30%, recent 20%.
        ranked = sorted(memory.data, key=lambda test: -(0.5 * test["failure_history"] + 0.3 * test["proximity"]
                                                        + 0.2 * test["recently_failed"]))
        budget_s, selected, used = ctx.policy.ci_budget_minutes * 60, [], 0.0
        for test in ranked:
            if used + test["duration_s"] <= budget_s:
                selected.append(test)
                used += test["duration_s"]
        return Step(selected, f"Chose {len(selected)} of {len(memory.data):,} tests that fit the "
                              f"{ctx.policy.ci_budget_minutes}-minute budget, riskiest first.")

    async def act(self, ctx: StageContext, seen: Step, memory: Step, plan: Step) -> Step:
        ctx.use_tool("ci.run", simulated=True, detail="runs the selected tests before and after the fix")
        run = tools.run_ci(plan.data, ctx.seed, seen.data)
        faults = run["failed_positions"]
        score = napfd(faults, num_tests=len(plan.data), total_faults=len(faults)) if plan.data else 1.0
        return Step({**run, "napfd": round(score, 3)},
                    f"Before the fix, {len(faults)} selected test(s) failed (first at position "
                    f"{faults[0] if faults else '-'}); with the fix all {len(plan.data)} pass.")

    def report(self, ctx, seen, memory, plan, result) -> dict[str, Any]:
        selected, run = plan.data, result.data
        checks = ["Run the reproduction case", "Run focused regression tests", "Run the full suite before release"]
        if ctx.guidance:
            checks += list(ctx.guidance.get("requested_changes", []))
        return {"suite_size": len(memory.data), "selected_tests": len(selected),
                "budget_minutes": ctx.policy.ci_budget_minutes, "duration_minutes": run["duration_minutes"],
                "selection_method": "risk-aware order: failure history 50%, closeness to the change 30%, "
                                    "recent failures 20%",
                "top_selected": [test["test_id"] for test in selected[:5]],
                "napfd": run["napfd"], "napfd_note": "how early the failing tests ran (1.0 = first)",
                "faults_found_before_fix": len(run["failed_positions"]), "tests_executed": len(selected),
                "passed": len(selected), "failed": 0, "flaky_retried": run["flaky_retried"], "regressions": [],
                "pass_fail": "passed", "recommended_checks": list(dict.fromkeys(checks)),
                "decisions": [decision("pr_merge", False, "human_checkpoint", ctx.policy,
                                       tests=len(selected), napfd=run["napfd"])],
                "summary": f"Ran {len(selected)} of {len(memory.data):,} tests in {run['duration_minutes']} min "
                           f"(NAPFD {run['napfd']}); all pass with the fix. Merge needs a code review."}


class WorkerDeploy(StageAgent):
    stage, agent_id, family = "deployment", "Worker-Deploy", "Worker"
    simulation_note = SIMULATED

    async def perceive(self, ctx: StageContext) -> Step:
        qa = ctx.outputs.get("qa", {})
        stats = ctx.outputs.get("implementation", {}).get("draft_pr", {}).get("diff_stats", {})
        return Step({"service": _top_suspect(ctx), "qa": qa, "stats": stats},
                    f"Merged change ready; QA {qa.get('pass_fail', 'unknown')} on {qa.get('tests_executed', 0)} tests.")

    async def remember(self, ctx: StageContext, seen: Step) -> Step:
        ctx.use_tool("deploy.history", simulated=True, detail=seen.data["service"])
        history = tools.deployment_history(seen.data["service"], ctx.seed)
        return Step(history, f"{seen.data['service']} had {history['rollbacks']} rollbacks in "
                             f"{history['deployments_last_90_days']} recent deployments.")

    async def reason(self, ctx: StageContext, seen: Step, memory: Step) -> Step:
        stats, qa = seen.data["stats"], seen.data["qa"]
        executed = max(1, qa.get("tests_executed", 1))
        factors = {"change_size": round(min(1.0, (stats.get("additions", 0) + stats.get("deletions", 0)) / 250), 3),
                   "qa_failure_rate": round(qa.get("failed", 0) / executed, 3),
                   "critical_service": 1.0 if seen.data["service"] in tools.CRITICAL_SERVICES else 0.0,
                   "rollback_history": round(min(1.0, memory.data["rollback_rate"] * 4), 3)}
        weights = {"change_size": 0.30, "qa_failure_rate": 0.30, "critical_service": 0.15, "rollback_history": 0.25}
        risk = round(sum(weights[name] * value for name, value in factors.items()), 2)
        allowed = canary_autonomous(risk, ctx.policy)
        return Step({"risk": risk, "factors": factors, "weights": weights, "autonomous": allowed},
                    f"Release risk score {risk} (limit {ctx.policy.canary_risk_max:.2f}): the "
                    f"{ctx.policy.canary_percent}% canary {'may start on its own' if allowed else 'needs a human'}.")

    async def act(self, ctx: StageContext, seen: Step, memory: Step, plan: Step) -> Step:
        if not plan.data["autonomous"]:
            return Step(None, "Waiting for a human before starting the canary.")
        canary = run_canary(ctx, seen.data["service"], plan.data["risk"])
        return Step(canary, f"Ran the {canary['percent']}% canary for {canary['observe_minutes']} minutes: "
                            f"{canary['status'].replace('_', ' ')}.")

    def report(self, ctx, seen, memory, plan, result) -> dict[str, Any]:
        canary = result.data or {"percent": ctx.policy.canary_percent, "status": "awaiting_review",
                                 "observe_minutes": ctx.policy.canary_observe_minutes, "slo_breach": None,
                                 "metrics": None, "deployment_id": None}
        failed = canary["status"] == "rolled_back"
        return {"risk_score": plan.data["risk"], "risk_factors": plan.data["factors"],
                "risk_weights": plan.data["weights"], "canary": canary,
                "full_release": {"status": "blocked" if failed else "awaiting_signoff", "deployment_id": None,
                                 "human_approved": False},
                "rollback_plan": f"Route traffic back to the previous {seen.data['service']} version "
                                 "(automatic on an SLO breach).",
                "decisions": [decision("canary_review", plan.data["autonomous"], "low_risk" if plan.data["autonomous"]
                                       else "risk_above_limit", ctx.policy, risk_score=plan.data["risk"],
                                       canary_risk_max=ctx.policy.canary_risk_max),
                              decision("release_signoff", False, "canary_failed" if failed else "human_checkpoint",
                                       ctx.policy, canary=canary["status"])],
                "summary": f"Risk {plan.data['risk']}; canary {canary['status'].replace('_', ' ')}. "
                           + ("Release blocked." if failed else "Full release needs a sign-off.")}


def run_canary(ctx: StageContext, service: str, risk: float) -> dict[str, Any]:
    """Start the small canary and record it; an SLO breach rolls it back automatically."""
    ctx.use_tool("deploy.canary", simulated=True, detail=f"{ctx.policy.canary_percent}% of traffic")
    canary = tools.run_canary(service, ctx.seed, ctx.policy.canary_percent, regression=False)
    deployment_id = f"DEP-{ctx.ticket['ticket_id']}-canary-r{ctx.revision}"
    ctx.deps.repository.save_deployment({
        "deployment_id": deployment_id,
        "change_id": ctx.outputs.get("implementation", {}).get("draft_pr", {}).get("change_id"),
        "ticket_id": ctx.ticket["ticket_id"], "environment": "canary",
        "strategy": f"canary-{ctx.policy.canary_percent}", "risk_score": risk,
        "status": "rolled_back" if canary["slo_breach"] else "canary_passed", "human_approved": False,
        "slo_breach": canary["slo_breach"]})
    return {**canary, "deployment_id": deployment_id}

