"""Scout-Monitor: simulated telemetry, anomalies and the feedback loop back to triage."""
import asyncio

from agents import tools
from agents.tests.helpers import fixed_triage, interpret_as_given, walk


def test_telemetry_is_deterministic_and_the_flash_sale_shows_an_anomaly():
    flash = tools.telemetry("flash_sale", 42)
    assert flash == tools.telemetry("flash_sale", 42)
    assert {item["service"] for item in flash["anomalies"]} == {"payment-db"}
    assert all(item["z"] >= 3 for item in flash["anomalies"])
    assert [step["percent"] for step in flash["canary_steps"]] == [5, 25, 50, 100]
    assert tools.telemetry("normal", 42)["anomalies"] == []


def test_an_alert_becomes_one_ticket_even_if_raised_twice(make_pipeline):
    pipeline = make_pipeline()
    anomaly = tools.telemetry("flash_sale", 42)["anomalies"][0]
    first = asyncio.run(pipeline.follow_up_from_anomaly(anomaly))
    again = asyncio.run(pipeline.follow_up_from_anomaly(anomaly))
    assert first["ticket_id"] == again["ticket_id"]
    assert first["channel"] == "monitoring" and first["component"] in {"payment", "other", "app"}


def test_a_post_release_regression_opens_a_follow_up_ticket(make_pipeline):
    pipeline = make_pipeline(classify=fixed_triage("Low", 0.82), interpret=interpret_as_given)
    ticket_id = asyncio.run(pipeline.create_ticket(feedback_id="FB-060",
                                                   options={"simulate_regression": True}))["ticket_id"]
    final, _gates = asyncio.run(walk(pipeline, ticket_id))
    monitoring = final["agent_outputs"]["monitoring"]
    assert monitoring["anomalies"] and monitoring["follow_up_ticket_id"] in final["follow_up_ticket_ids"]
    follow_up = pipeline.snapshot(monitoring["follow_up_ticket_id"])
    assert follow_up["parent_ticket_id"] == ticket_id and follow_up["channel"] == "monitoring"

    # A follow-up that regresses again does not spawn another ticket (no endless loop).
    pipeline.records[follow_up["ticket_id"]]["options"]["simulate_regression"] = True
    again, _ = asyncio.run(walk(pipeline, follow_up["ticket_id"]))
    assert again["agent_outputs"]["monitoring"]["follow_up_ticket_id"] is None
