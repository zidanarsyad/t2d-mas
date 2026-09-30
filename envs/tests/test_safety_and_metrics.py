import numpy as np
import pytest

from envs.ci_data import generate_simulated_cycles
from envs.metrics import deployment_outcome_reward, napfd, prioritization_reward
from envs.safety import authorize_deployment_action


def test_full_action_requires_human_approval() -> None:
    executed, blocked = authorize_deployment_action("full", human_approved=False)
    assert executed == "hold"
    assert blocked is True


def test_full_action_is_allowed_with_explicit_approval() -> None:
    executed, blocked = authorize_deployment_action("full", human_approved=True)
    assert executed == "full"
    assert blocked is False


def test_napfd_reward_terms_are_reproducible() -> None:
    score = napfd([1, 4], num_tests=10, total_faults=3)
    assert score == pytest.approx((2 / 3) - (5 / 30) + (2 / 3) / 20)
    assert prioritization_reward(score, 20.0, 0.005) == pytest.approx(score - 0.1)
    assert deployment_outcome_reward(rollback=False, hours_delayed=2) == pytest.approx(0.6)
    assert deployment_outcome_reward(rollback=True, hours_delayed=2) == pytest.approx(-5.4)


def test_synthetic_ci_generator_is_seeded() -> None:
    first = generate_simulated_cycles(num_cycles=200, num_tests=8, seed=42)
    second = generate_simulated_cycles(num_cycles=200, num_tests=8, seed=42)
    assert first.dataset_version == second.dataset_version
    assert len(first.cycles) == 200
    assert np.array_equal(first.cycles[5].observations, second.cycles[5].observations)
    assert np.array_equal(first.cycles[5].fault_mask, second.cycles[5].fault_mask)


def test_environment_guard_blocks_full_without_approval_when_gymnasium_available() -> None:
    pytest.importorskip("gymnasium")
    from envs.canary_deploy import CanaryDeployEnv

    env = CanaryDeployEnv()
    env.reset(seed=42)
    _obs, _reward, _terminated, _truncated, info = env.step(3)
    assert info["requested_action"] == "full"
    assert info["executed_action"] == "hold"
    assert info["approval_required"] is True
    assert info["deployment_started"] is False
