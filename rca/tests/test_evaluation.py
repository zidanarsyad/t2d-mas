import pytest

from rca.evaluation import ranking_metrics
from rca.baseline import pagerank_scores


def test_top_k_and_reciprocal_rank() -> None:
    result = ranking_metrics([0.2, 0.9, 0.7, 0.1], [2])
    assert result == {"top1_accuracy": 0.0, "top3_accuracy": 1.0, "mrr": pytest.approx(0.5)}


def test_pagerank_is_normalized() -> None:
    scores = pagerank_scores([[0, 1], [1, 2]], [2.0, 1.0], num_nodes=3)
    assert float(scores.sum()) == pytest.approx(1.0)
    assert scores[2] > scores[0]
