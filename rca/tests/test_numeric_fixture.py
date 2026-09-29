"""The requested two-feature arithmetic fixture from the assignment."""
import pytest

from rca.numerics import reference_mean_sage_scores


def test_reference_graphsage_scores() -> None:
    scores = reference_mean_sage_scores(
        features=[[2.1, 1.0], [2.6, 1.2], [3.4, 2.8]],
        directed_edges=[(0, 1), (1, 2)],
        weight=[[0.5, 0.0], [0.0, 0.5]],
        readout=[0.6, 0.4],
    )
    assert scores == pytest.approx([1.850, 2.225, 2.600], abs=1e-3)


def test_pyg_model_matches_fixed_reference_weights_when_available() -> None:
    torch = pytest.importorskip("torch")
    pytest.importorskip("torch_geometric")
    from rca.model import GraphSAGEScorer

    # The numerical report example specifies a single fixed aggregator, so fix
    # layer one to W=.5I and make layer two a root identity readout stage.
    model = GraphSAGEScorer(in_channels=2, hidden_channels=2, dropout=0.0)
    with torch.no_grad():
        model.conv1.lin_root.weight.copy_(0.5 * torch.eye(2))
        model.conv1.lin_neigh.weight.copy_(0.5 * torch.eye(2))
        model.conv1.lin_root.bias.zero_()
        model.conv2.lin_root.weight.copy_(torch.eye(2))
        model.conv2.lin_neigh.weight.zero_()
        model.conv2.lin_root.bias.zero_()
        model.readout.weight.copy_(torch.tensor([[0.6, 0.4]]))
        model.readout.bias.zero_()
    x = torch.tensor([[2.1, 1.0], [2.6, 1.2], [3.4, 2.8]])
    # The directed trace remains A->B->C; message passing adds reverse context.
    edge_index = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]])
    scores = model(x, edge_index, torch.ones(edge_index.size(1)))
    assert scores.tolist() == pytest.approx([1.850, 2.225, 2.600], abs=1e-3)
