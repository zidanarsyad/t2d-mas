"""Evaluate learned and heuristic CI/CD policies; write a versioned CSV and chart."""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .canary_deploy import CanaryDeployEnv
from .ci_data import CIData, CICycle, generate_simulated_cycles, load_public_ci_csv
from .safety import CANARY_ACTIONS
from .test_prioritization import TestPrioritizationEnv


def failed_newest_scores(cycle: CICycle) -> np.ndarray:
    """Prefer tests whose last recorded failure was most recent (ties: fail rate)."""
    # Age is hidden historical metadata for a transparent, deterministic baseline.
    age = cycle.cycles_since_last_failure
    recency = 1.0 / (1.0 + age)
    return (recency + 0.001 * cycle.observations[:, 2]).astype(np.float32)


def evaluate_test_policy(name: str, cycles: tuple[CICycle, ...], dataset_version: str,
                         seed: int, model=None, baseline: str | None = None) -> dict:
    rng = np.random.default_rng(seed)
    napfd_values, first_failure_times = [], []
    for index, cycle in enumerate(cycles):
        env = TestPrioritizationEnv(cycles=[cycle], dataset_version=dataset_version)
        observation, _ = env.reset(seed=seed + index)
        if model is not None:
            action, _ = model.predict(observation, deterministic=True)
        elif baseline == "random_order":
            action = rng.random(env.num_tests).astype(np.float32)
        else:
            action = failed_newest_scores(cycle)
        _obs, _reward, _terminated, _truncated, info = env.step(action)
        napfd_values.append(info["napfd"])
        if info["time_to_first_failure_seconds"] is not None:
            first_failure_times.append(info["time_to_first_failure_seconds"])
        env.close()
    return {
        "environment": "test_prioritization",
        "policy": name,
        "episodes": len(cycles),
        "napfd": float(np.mean(napfd_values)),
        "time_to_first_failure_seconds": (float(np.mean(first_failure_times))
                                           if first_failure_times else math.nan),
        "rollback_ratio": math.nan,
        "dataset_version": dataset_version,
    }


def risk_aware_canary_action(observation: np.ndarray) -> int:
    risk, _diff, qa_pass, _hour, _rollbacks = observation
    if risk >= 0.60 or qa_pass < 0.85:
        return CANARY_ACTIONS.index("canary_5")
    if risk < 0.18 and qa_pass >= 0.97:
        return CANARY_ACTIONS.index("full")
    return CANARY_ACTIONS.index("canary_25")


def evaluate_deploy_policy(name: str, episodes: int, seed: int,
                           model=None, baseline: str | None = None) -> dict:
    random_actions = np.random.default_rng(seed + 99)
    rollbacks = 0
    failures_in_window = []
    for episode in range(episodes):
        env = CanaryDeployEnv()
        observation, _ = env.reset(seed=seed + episode,
                                   options={"human_approved": True})
        terminated = truncated = False
        total_delay_hours = 0.0
        while not (terminated or truncated):
            if model is not None:
                action, _ = model.predict(observation, deterministic=True)
                action = int(np.asarray(action).reshape(-1)[0])
            elif baseline == "random_action":
                action = int(random_actions.integers(0, len(CANARY_ACTIONS)))
            else:
                action = risk_aware_canary_action(observation)
            observation, _reward, terminated, truncated, info = env.step(action)
            if info["executed_action"] == "hold":
                total_delay_hours += 1.0
            if info["deployment_started"]:
                if info["rollback"]:
                    rollbacks += 1
                    failures_in_window.append(
                        total_delay_hours * 3600
                        + float(info["time_to_first_failure_minutes"]) * 60
                    )
                break
        env.close()
    return {
        "environment": "canary_deploy",
        "policy": name,
        "episodes": episodes,
        "napfd": math.nan,
        "time_to_first_failure_seconds": (float(np.mean(failures_in_window))
                                           if failures_in_window else math.nan),
        "rollback_ratio": rollbacks / episodes,
        "dataset_version": "",
    }


def _write_outputs(rows: list[dict], output_dir: Path, dataset_version: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "rl_evaluation.csv"
    columns = ["environment", "policy", "episodes", "napfd",
               "time_to_first_failure_seconds", "rollback_ratio", "dataset_version"]
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ("" if isinstance(row[key], float) and math.isnan(row[key])
                                   else row[key]) for key in columns})

    ci_rows = [row for row in rows if row["environment"] == "test_prioritization"]
    deploy_rows = [row for row in rows if row["environment"] == "canary_deploy"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    axes[0].bar([row["policy"] for row in ci_rows], [row["napfd"] for row in ci_rows],
                color="#4263eb")
    axes[0].set_title("Test prioritization NAPFD")
    axes[0].set_ylim(0, 1)
    axes[1].bar([row["policy"] for row in ci_rows],
                [row["time_to_first_failure_seconds"] for row in ci_rows], color="#f08c00")
    axes[1].set_title("CI time to first failure (s)")
    axes[2].bar([row["policy"] for row in deploy_rows],
                [row["rollback_ratio"] for row in deploy_rows], color="#e03131")
    axes[2].set_title("Canary rollback ratio")
    axes[2].set_ylim(0, 1)
    for ax in axes:
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.2)
    fig.suptitle(f"RL policy evaluation | dataset_version={dataset_version}")
    fig.tight_layout()
    fig.savefig(output_dir / "rl_evaluation.png", dpi=160,
                metadata={"Description": f"dataset_version={dataset_version}"})
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", default="rl_outputs/models")
    parser.add_argument("--data", help="Optional local or URL public CI results CSV")
    parser.add_argument("--output-dir", default="rl_outputs/evaluation")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--episodes", type=int, default=100)
    args = parser.parse_args()
    try:
        from stable_baselines3 import DQN, PPO
    except ImportError as exc:
        raise SystemExit("Install envs/requirements.txt to evaluate PPO and DQN") from exc
    data: CIData = (load_public_ci_csv(args.data) if args.data
                    else generate_simulated_cycles(num_cycles=200, seed=args.seed))
    if len(data.cycles) < 1 or args.episodes < 1:
        raise SystemExit("Evaluation needs at least one CI cycle and one deployment episode")
    models_dir = Path(args.models_dir)
    required_models = ["ppo_test_prioritization", "ppo_canary", "dqn_canary"]
    missing = [name for name in required_models if not (models_dir / f"{name}.zip").exists()]
    if missing:
        raise SystemExit(f"Missing trained model(s): {', '.join(missing)}; run python -m envs.train_rl first")
    ppo_tests = PPO.load(models_dir / "ppo_test_prioritization")
    ppo_canary = PPO.load(models_dir / "ppo_canary")
    dqn_canary = DQN.load(models_dir / "dqn_canary")
    # Match training's chronological holdout so reported CI scores use unseen cycles.
    evaluation_cycles = data.cycles[max(1, int(len(data.cycles) * 0.8)):]
    if not evaluation_cycles:
        evaluation_cycles = data.cycles
    rows = [
        evaluate_test_policy("ppo", evaluation_cycles, data.dataset_version, args.seed, model=ppo_tests),
        evaluate_test_policy("random_order", evaluation_cycles, data.dataset_version,
                             args.seed, baseline="random_order"),
        evaluate_test_policy("failed_newest_first", evaluation_cycles, data.dataset_version,
                             args.seed, baseline="failed_newest_first"),
    ]
    deploy_rows = [
        evaluate_deploy_policy("ppo", args.episodes, args.seed, model=ppo_canary),
        evaluate_deploy_policy("dqn", args.episodes, args.seed, model=dqn_canary),
        evaluate_deploy_policy("random_action", args.episodes, args.seed,
                               baseline="random_action"),
        evaluate_deploy_policy("risk_aware_canary", args.episodes, args.seed,
                               baseline="risk_aware_canary"),
    ]
    # A deploy-row version describes both the CI source and the fixed deployment seed.
    for row in deploy_rows:
        row["dataset_version"] = f"{data.dataset_version}:canary-seed-{args.seed}"
    rows.extend(deploy_rows)
    _write_outputs(rows, Path(args.output_dir), data.dataset_version)
    print(f"Saved evaluation CSV and chart; dataset_version={data.dataset_version}")


if __name__ == "__main__":
    main()
