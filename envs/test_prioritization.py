"""Gymnasium test-prioritization environment inspired by Retecs."""
__test__ = False  # This module defines an environment; it is not a pytest test file.
from __future__ import annotations

from collections.abc import Sequence

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .ci_data import CIData, CICycle, generate_simulated_cycles
from .metrics import napfd, prioritization_reward


class TestPrioritizationEnv(gym.Env):
    """Choose a continuous priority score for every test under a time budget.

    One episode schedules one CI cycle. Action scores are clipped to [0, 1], tests
    are sorted by descending score, and any test that does not fit is skipped.
    """

    metadata = {"render_modes": []}

    def __init__(self, cycles: Sequence[CICycle] | None = None,
                 budget_seconds: float = 60.0, lambda_time: float = 0.005,
                 num_cycles: int = 200, num_tests: int = 20, seed: int = 42,
                 dataset_version: str | None = None) -> None:
        super().__init__()
        if budget_seconds <= 0 or lambda_time < 0:
            raise ValueError("budget_seconds must be positive and lambda_time non-negative")
        if cycles is None:
            generated: CIData = generate_simulated_cycles(num_cycles, num_tests, seed)
            cycles = generated.cycles
            dataset_version = dataset_version or generated.dataset_version
        if not cycles:
            raise ValueError("cycles cannot be empty")
        self.cycles = tuple(cycles)
        self.dataset_version = dataset_version or "external-ci-data"
        self.budget_seconds = float(budget_seconds)
        self.lambda_time = float(lambda_time)
        self.num_tests = len(self.cycles[0].test_ids)
        self.observation_space = spaces.Box(
            low=np.asarray([0, 0, 0, 0, 0], dtype=np.float32),
            high=np.asarray([1, np.inf, 1, 1, 1], dtype=np.float32),
            shape=(self.num_tests, 5), dtype=np.float32,
        )
        self.action_space = spaces.Box(low=0.0, high=1.0,
                                       shape=(self.num_tests,), dtype=np.float32)
        self._cursor = 0
        self._cycle: CICycle | None = None

    @property
    def current_cycle(self) -> CICycle:
        if self._cycle is None:
            raise RuntimeError("Call reset() before accessing current_cycle")
        return self._cycle

    def reset(self, *, seed: int | None = None,
              options: dict | None = None) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        if seed is not None:
            self._cursor = 0
        self._cycle = self.cycles[self._cursor % len(self.cycles)]
        self._cursor += 1
        return self._cycle.observations.copy(), {
            "dataset_version": self.dataset_version,
            "cycle_index": (self._cursor - 1) % len(self.cycles),
        }

    def step(self, action: np.ndarray):
        if self._cycle is None:
            raise RuntimeError("Call reset() before step()")
        scores = np.asarray(action, dtype=np.float32).reshape(-1)
        if scores.shape != (self.num_tests,):
            raise ValueError(f"Expected {self.num_tests} priority scores")
        scores = np.nan_to_num(scores, nan=0.0, posinf=1.0, neginf=0.0)
        scores = np.clip(scores, 0.0, 1.0)
        order = np.argsort(-scores, kind="stable")
        elapsed = 0.0
        executed: list[int] = []
        for test_index in order:
            duration = float(self._cycle.durations[test_index])
            if duration <= self.budget_seconds - elapsed:
                executed.append(int(test_index))
                elapsed += duration
        rank_by_test = {int(test_index): rank for rank, test_index in enumerate(order, start=1)}
        detected_ranks = [rank_by_test[index] for index in executed
                          if bool(self._cycle.fault_mask[index])]
        total_faults = int(self._cycle.fault_mask.sum())
        score = napfd(detected_ranks, self.num_tests, total_faults)
        reward = prioritization_reward(score, elapsed, self.lambda_time)
        first_failure = None
        elapsed_to_test = 0.0
        for test_index in executed:
            elapsed_to_test += float(self._cycle.durations[test_index])
            if self._cycle.fault_mask[test_index]:
                first_failure = elapsed_to_test
                break
        info = {
            "dataset_version": self.dataset_version,
            "napfd": score,
            "total_execution_seconds": elapsed,
            "time_to_first_failure_seconds": first_failure,
            "total_faults": total_faults,
            "faults_detected": len(detected_ranks),
            "executed_test_ids": [self._cycle.test_ids[index] for index in executed],
            "executed_test_indices": executed,
            "priority_order": order.tolist(),
            "reward_napfd_term": score,
            "reward_time_penalty": self.lambda_time * elapsed,
        }
        return self._cycle.observations.copy(), reward, True, False, info
