import pytest

from agents.broker_assign import Proposal, select_winner, utility


def test_report_cnp_utilities_and_winner():
    bids = [Proposal("W1", 0.90, 0.80, 0.40),
            Proposal("W2", 0.70, 0.20, 0.50),
            Proposal("W3", 0.50, 0.10, 0.30)]
    assert [utility(b.skill, b.load, b.cost) for b in bids] == pytest.approx([0.63, 0.69, 0.66])
    winner, rejected = __import__("asyncio").run(select_winner(bids))
    assert winner.worker_id == "W2"
    assert [bid.worker_id for bid in rejected] == ["W3", "W1"]
