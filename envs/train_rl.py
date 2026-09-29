"""Train PPO/DQN policies and save reproducible learning-curve artifacts."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import gymnasium as gym
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .canary_deploy import CanaryDeployEnv
from .ci_data import CIData, generate_simulated_cycles, load_public_ci_csv
from .test_prioritization import TestPrioritizationEnv


class SimulatedHumanApproval(gym.Wrapper):
    """Supply an explicit simulated human approval signal during offline training."""

    def reset(self, *, seed=None, options=None):
        approved_options = dict(options or {})
        approved_options["human_approved"] = True
        return self.env.reset(seed=seed, options=approved_options)


def make_approved_canary_env() -> SimulatedHumanApproval:
    # Offline training may explore full rollout only in explicitly approved episodes.
    return SimulatedHumanApproval(CanaryDeployEnv())


try:
    from stable_baselines3.common.callbacks import BaseCallback
except ImportError:
    BaseCallback = object


class LearningCurveCallback(BaseCallback):
    """Write per-episode reward CSV and a PNG chart with dataset provenance."""

    def __init__(self, output_dir: Path, name: str, dataset_version: str) -> None:
        if BaseCallback is object:
            raise RuntimeError("Install envs/requirements.txt to train reinforcement-learning models")
        super().__init__(verbose=0)
        self.output_dir = output_dir
        self.name = name
        self.dataset_version = dataset_version
        self.episode_rewards: list[float] = []
        self._running_rewards: np.ndarray | None = None

    def _on_training_start(self) -> None:
        self._running_rewards = np.zeros(self.training_env.num_envs, dtype=float)

    def _on_step(self) -> bool:
        rewards = np.asarray(self.locals["rewards"], dtype=float).reshape(-1)
        dones = np.asarray(self.locals["dones"], dtype=bool).reshape(-1)
        self._running_rewards += rewards
        for index in np.flatnonzero(dones):
            self.episode_rewards.append(float(self._running_rewards[index]))
            self._running_rewards[index] = 0.0
        return True

    def _on_training_end(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = self.output_dir / f"{self.name}_learning_curve.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["episode", "reward", "dataset_version"])
            writer.writeheader()
            for index, reward in enumerate(self.episode_rewards, start=1):
                writer.writerow({"episode": index, "reward": reward,
                                 "dataset_version": self.dataset_version})
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(np.arange(1, len(self.episode_rewards) + 1), self.episode_rewards,
                linewidth=1.0, alpha=0.8)
        ax.set(title=f"{self.name} learning curve | {self.dataset_version}",
               xlabel="Episode", ylabel="Episode reward")
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(self.output_dir / f"{self.name}_learning_curve.png", dpi=150,
                    metadata={"Description": f"dataset_version={self.dataset_version}"})
        plt.close(fig)


def load_data(path: str | None, seed: int) -> CIData:
    return load_public_ci_csv(path) if path else generate_simulated_cycles(seed=seed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", help="Optional local or URL CI CSV; otherwise simulate 200 cycles")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timesteps", type=int, default=20_000)
    parser.add_argument("--output-dir", default="rl_outputs")
    args = parser.parse_args()
    try:
        from stable_baselines3 import DQN, PPO
    except ImportError as exc:
        raise SystemExit("Install envs/requirements.txt to train PPO and DQN") from exc
    if args.timesteps < 1:
        raise SystemExit("--timesteps must be positive")

    data = load_data(args.data, args.seed)
    if len(data.cycles) < 2:
        raise SystemExit("Training needs at least two CI cycles for train/evaluation split")
    split_at = max(1, int(len(data.cycles) * 0.8))
    training_cycles, evaluation_cycles = data.cycles[:split_at], data.cycles[split_at:]
    output_dir = Path(args.output_dir)
    models_dir, curves_dir = output_dir / "models", output_dir / "curves"
    models_dir.mkdir(parents=True, exist_ok=True)

    test_env = TestPrioritizationEnv(cycles=training_cycles,
                                     dataset_version=data.dataset_version)
    test_model = PPO("MlpPolicy", test_env, seed=args.seed, verbose=0,
                     n_steps=128, batch_size=64)
    test_model.learn(args.timesteps,
                     callback=LearningCurveCallback(curves_dir, "ppo_test_prioritization",
                                                    data.dataset_version))
    test_model.save(models_dir / "ppo_test_prioritization")
    test_env.close()

    for algorithm_name, algorithm in (("ppo", PPO), ("dqn", DQN)):
        canary_env = make_approved_canary_env()
        if algorithm_name == "ppo":
            model = algorithm("MlpPolicy", canary_env, seed=args.seed, verbose=0,
                              n_steps=128, batch_size=64)
        else:
            model = algorithm("MlpPolicy", canary_env, seed=args.seed, verbose=0,
                              learning_starts=128, buffer_size=10_000,
                              batch_size=64, train_freq=4, target_update_interval=250)
        curve_name = f"{algorithm_name}_canary"
        model.learn(args.timesteps,
                    callback=LearningCurveCallback(curves_dir, curve_name,
                                                   data.dataset_version))
        model.save(models_dir / curve_name)
        canary_env.close()

    manifest = {
        "dataset_version": data.dataset_version,
        "seed": args.seed,
        "timesteps_per_model": args.timesteps,
        "training_cycles": len(training_cycles),
        "evaluation_cycles": len(evaluation_cycles),
        "models": ["ppo_test_prioritization", "ppo_canary", "dqn_canary"],
        "canary_training_approval": "explicit simulated human_approved=True per episode",
    }
    (output_dir / "training_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Saved models and curves; dataset_version={data.dataset_version}")


if __name__ == "__main__":
    main()
