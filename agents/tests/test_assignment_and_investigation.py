"""Contract Net routing and the Scout-Log mobile investigation across six data nodes."""
import asyncio
import json

from agents import tools
from agents.brokers import BrokerAssign
from agents.mobility import should_migrate
from agents.tests.helpers import fixed_triage


def run_until(pipeline, ticket_id, stage):
    """Advance until `stage` has produced its output (the tickets here never pause)."""
    async def run():
        snapshot = pipeline.snapshot(ticket_id)
        while stage not in snapshot["agent_outputs"]:
            assert snapshot["status"] == "running", snapshot["status"]
            snapshot = await pipeline.advance(ticket_id)
        return snapshot
    return asyncio.run(run())


def test_the_squad_that_knows_the_area_wins_and_actually_investigates(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("Low", 0.82))
    payment = asyncio.run(pipeline.create_ticket(feedback_id="FB-031"))["ticket_id"]
    login = asyncio.run(pipeline.create_ticket(feedback_id="FB-014"))["ticket_id"]
    paid = run_until(pipeline, payment, "investigation")
    signed_in = run_until(pipeline, login, "investigation")
    assert paid["assignee"] == "Worker-Investigate-Payments"
    assert signed_in["assignee"] == "Worker-Investigate-Mobile"
    assert paid["agent_outputs"]["investigation"]["agent"] == paid["assignee"]
    accepted = [event for event in pipeline.audit.events if event.action == "agent_message"
                and event.details["performative"] == "accept-proposal" and event.ticket_id == payment]
    assert accepted[0].details["receivers"] == ["Worker-Investigate-Payments"]


def test_a_busy_squad_loses_the_auction():
    class Deps:
        @staticmethod
        def squad_load(_ticket_id):
            return {"Worker-Investigate-Payments": 3, "Worker-Investigate-Mobile": 0, "Worker-Investigate-Platform": 0}

    class Context:
        ticket, deps = {"ticket_id": "T-1", "component": "payment"}, Deps()

    agent = BrokerAssign()

    async def bids():
        seen = await agent.perceive(Context)
        memory = await agent.remember(Context, seen)
        return (await agent.reason(Context, seen, memory)).data

    proposals = asyncio.run(bids())
    best = max(proposals.values(), key=lambda proposal: proposal.score)
    assert best.worker_id == "Worker-Investigate-Platform"  # Payments knows payments but has 3 open tickets


def test_scout_log_visits_every_node_and_only_aggregates_come_back(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("Low", 0.82))
    ticket_id = asyncio.run(pipeline.create_ticket(feedback_id="FB-031"))["ticket_id"]
    investigation = run_until(pipeline, ticket_id, "investigation")["agent_outputs"]["investigation"]

    visits = investigation["node_visits"]
    assert [visit["node_id"] for visit in visits] == list(tools.NODE_SERVICE)
    for visit in visits:  # the report's rule decides, per node, whether the agent travels
        rule = visit["migration_rule"]
        assert rule["should_migrate"] == should_migrate(rule["log_mb"], 12, 2, 3)
        assert visit["mode"] == ("mobile_agent" if rule["should_migrate"] else "node_exporter")
    assert visits[-1]["mode"] == "node_exporter"  # node-6 holds only 30 MB, below the 42 MB break-even
    assert investigation["rca"]["top_suspect"] == "payment-db"
    assert investigation["raw_data_left_nodes"] is False
    assert investigation["bytes_moved"] == sum(v["bytes_sent"] + v["bytes_returned"] for v in visits)
    # Node logs carry fake customer e-mails; none may appear anywhere outside the nodes.
    assert "users.example.net" not in json.dumps(investigation)
    assert "users.example.net" not in str(pipeline.audit.events)
