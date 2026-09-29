"""Gymnasium canary-deployment environment with an explicit full-release gate."""
from __future__ import annotations

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .metrics import deployment_outcome_reward
from .safety import CANARY_ACTIONS, authorize_deployment_action


class CanaryDeployEnv(gym.Env):
    """Choose hold/canary/full while simulating a 30-minute SLO observation window.

    ``full`` is changed to ``hold`` unless a one-use human approval is explicitly
    supplied through ``reset(options={"human_approved": True})``.
    """

    metadata = {"render_modes": []}
    ACTIONS = CANARY_ACTIONS

    def __init__(self, max_delay_hours: int = 24) -> None:
        super().__init__()
        if max_delay_hours < 1:
            raise ValueError("max_delay_hours must be at least 1")
        self.max_delay_hours = max_delay_hours
        self.observation_space = spaces.Box(
            low=np.asarray([0, 0, 0, 0, 0], dtype=np.float32),
            high=np.asarray([1, 1, 1, 23, 30], dtype=np.float32),
            dtype=np.float32,
        )
        self.action_space = spaces.Discrete(len(self.ACTIONS))
        self.state = np.zeros(5, dtype=np.float32)
        self._hours_delayed = 0
        self._approval_available = False
        self._finished = False

    def reset(self, *, seed: int | None = None,
              options: dict | None = None) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        options = options or {}
        self._hours_delayed = 0
        self._finished = False
        self._approval_available = bool(options.get("human_approved", False))
        supplied_state = options.get("state")
        if supplied_state is None:
            self.state = np.asarray([
                self.np_random.uniform(0.02, 0.85),
                self.np_random.uniform(0.01, 0.8),
                self.np_random.uniform(0.75, 1.0),
                self.np_random.integers(0, 24),
                self.np_random.integers(0, 6),
            ], dtype=np.float32)
        else:
            self.state = np.asarray(supplied_state, dtype=np.float32).copy()
            if not self.observation_space.contains(self.state):
                raise ValueError("provided state is outside observation_space")
        return self.state.copy(), {
            "human_approved": self._approval_available,
            "simulated_window_minutes": 0,
        }

    def step(self, action: int):
        if self._finished:
            raise RuntimeError("Episode ended; call reset() before another step")
        requested_name = self.ACTIONS[int(action)] if 0 <= int(action) < len(self.ACTIONS) else None
        if requested_name is None:
            raise ValueError("action must be a valid discrete action index")
        executed_name, blocked = authorize_deployment_action(
            requested_name, self._approval_available
        )
        if requested_name == "full" and self._approval_available:
            # Human approval authorizes one full release, not future steps.
            self._approval_available = False
        if executed_name == "hold":
            self._hours_delayed += 1
            self.state[3] = (self.state[3] + 1) % 24
            truncated = self._hours_delayed >= self.max_delay_hours
            self._finished = truncated
            info = {
                "requested_action": requested_name,
                "executed_action": "hold",
                "approval_required": blocked,
                "human_approved": not blocked and requested_name == "full",
                "deployment_started": False,
                "rollback": False,
                "time_to_first_failure_minutes": None,
                "hours_delayed": self._hours_delayed,
                "simulated_window_minutes": 0,
            }
            return self.state.copy(), -0.2, False, truncated, info

        exposure = {"canary_5": 0.40, "canary_25": 0.70, "full": 1.0}[executed_name]
        risk, diff_size, qa_pass, _hour, rollback_count = map(float, self.state)
        violation_probability = np.clip(
            (0.30 * risk + 0.15 * diff_size + 0.30 * (1.0 - qa_pass)
             + 0.003 * rollback_count) * exposure,
            0.0, 0.95,
        )
        rollback = bool(self.np_random.random() < violation_probability)
        time_to_failure = (float(self.np_random.uniform(1.0, 30.0)) if rollback else None)
        # Hold already charged -0.2 per hour, so the terminal outcome is not double-counted.
        reward = deployment_outcome_reward(rollback)
        if rollback:
            self.state[4] = min(30.0, self.state[4] + 1.0)
        self._finished = True
        info = {
            "requested_action": requested_name,
            "executed_action": executed_name,
            "approval_required": False,
            "human_approved": requested_name == "full",
            "deployment_started": True,
            "rollback": rollback,
            "slo_violation": rollback,
            "violation_probability": float(violation_probability),
            "time_to_first_failure_minutes": time_to_failure,
            "hours_delayed": self._hours_delayed,
            "cumulative_delay_penalty": -0.2 * self._hours_delayed,
            "simulated_window_minutes": 30,
        }
        return self.state.copy(), reward, True, False, info
