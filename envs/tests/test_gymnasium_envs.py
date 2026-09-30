import numpy as np
import pytest


gym = pytest.importorskip("gymnasium")


def test_prioritization_budget_and_gymnasium_api() -> None:
    from gymnasium.utils.env_checker import check_env
    from envs.ci_data import CICycle
    from envs.test_prioritization import TestPrioritizationEnv

    cycle = CICycle(
        observations=np.zeros((3, 5), dtype=np.float32),
        durations=np.asarray([2.0, 2.0, 3.0], dtype=np.float32),
        fault_mask=np.asarray([True, False, True]),
        cycles_since_last_failure=np.asarray([1, 10, 2], dtype=np.float32),
        test_ids=("a", "b", "c"),
    )
    env = TestPrioritizationEnv(cycles=[cycle], budget_seconds=4.0, lambda_time=0.0)
    check_env(env, skip_render_check=True)
    env.reset(seed=42)
    _obs, _reward, terminated, truncated, info = env.step(np.asarray([0.9, 0.8, 0.1]))
    assert terminated is True
    assert truncated is False
    assert info["total_execution_seconds"] == 4.0
    assert info["faults_detected"] == 1


def test_unauthorized_full_never_deploys_in_environment() -> None:
    from envs.canary_deploy import CanaryDeployEnv

    env = CanaryDeployEnv()
    env.reset(seed=42)
    _obs, _reward, _terminated, _truncated, info = env.step(3)
    assert info["executed_action"] == "hold"
    assert info["deployment_started"] is False


def test_authorized_full_runs_a_30_minute_window() -> None:
    from envs.canary_deploy import CanaryDeployEnv

    env = CanaryDeployEnv()
    env.reset(seed=42, options={"human_approved": True,
                               "state": [0.1, 0.1, 1.0, 10.0, 0.0]})
    _obs, _reward, terminated, truncated, info = env.step(3)
    assert terminated is True
    assert truncated is False
    assert info["executed_action"] == "full"
    assert info["simulated_window_minutes"] == 30
