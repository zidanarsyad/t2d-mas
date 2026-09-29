from agents.audit import MemoryAuditSink
from agents.flash_sale import run_flash_sale


def test_flash_sale_scenario_reproduces_report_timeline():
    sink = MemoryAuditSink()
    events = run_flash_sale(sink)
    assert [event.time_label for event in events] == [
        "00:00", "00:12", "00:20", "01:30", "01:35", "01:40", "02:05",
        "02:20", "02:50", "03:05", "03:15", "03:25", "04:00", "04:30",
    ]
    assert events[0].result == {"ticket_count": 2143, "parent": "TCK-1042", "duplicates_linked": 2142}
    assert events[2].result["waiting"] == "autonomy_gate"
    assert events[4].result["worker"] == "W2" and events[4].result["utility"] == 0.69
    assert events[5].result["total_bytes_mb"] == 84
    assert events[5].result["elapsed_s"] == 27
    assert events[9].result["napfd"] == 0.94
    assert events[11].result["slo_breach"] is False
    assert events[-1].result["ticket_closed"] is True
    assert any(event.action == "full_deploy" and event.human_approved for event in sink.events)
    assert all(event.correlation_id == "TCK-1042" for event in sink.events)
