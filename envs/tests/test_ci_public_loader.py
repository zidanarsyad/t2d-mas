from pathlib import Path

from envs.ci_data import load_public_ci_csv


def test_public_ci_csv_loader() -> None:
    source = Path(__file__).parent / "fixtures" / "ci_public.csv"
    dataset = load_public_ci_csv(source)
    assert len(dataset.cycles) == 2
    assert dataset.cycles[0].observations.shape == (2, 5)
    assert dataset.cycles[0].fault_mask.tolist() == [False, True]
    assert dataset.cycles[1].observations[1, 2] == 1.0
