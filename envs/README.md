# CI/CD reinforcement-learning environments

The package provides a small, seeded simulation for the T2D-MAS class project. It follows Gymnasium's `reset(seed=...)` and five-value `step()` interface. PPO is trained on continuous test-priority scores and on the discrete canary environment; DQN is trained on the discrete canary environment, since SB3 DQN requires a discrete action space.

## Environments and rewards

`TestPrioritizationEnv` exposes a matrix with one row per test and these columns: normalized duration, cycles since execution, historical failure ratio, flaky flag, and diff proximity. Its continuous action contains one score per test. Scores are clipped to [0, 1], sorted descending, and tests that do not fit the remaining budget are skipped. For detected fault ranks `TF_i`, suite size `n`, and all known faults `m`, NAPFD is:

```text
P - sum(TF_i) / (n * m) + P / (2 * n)
P = number of detected faults / m
reward = NAPFD - lambda_time * total_execution_seconds
```

If a cycle has no fault labels, NAPFD is defined as 1.0. The default is a 60-second budget and `lambda_time=0.005` reward units per second. `failed_newest_first` uses hidden historical failure age for the baseline; that age is not added to the requested five-feature policy observation.

`CanaryDeployEnv` state columns are risk score, normalized diff size, QA pass ratio, hour of day, and rollback count for 30 days. Action indices map to `hold`, `canary_5`, `canary_25`, and `full`. A hold step advances one hour and returns -0.2. After rollout, a 30-minute SLO window returns +1 for no violation or -5 for rollback. Full rollout is downgraded to hold unless an explicit, one-use `human_approved=True` signal was supplied in `reset(options=...)`.

Training uses `SimulatedHumanApproval`, which provides that explicit signal inside offline simulation so PPO/DQN can explore full rollout. The regular environment defaults to no approval; an agent action alone cannot authorize a full rollout.

## Data

`generate_simulated_cycles(seed=42)` produces 200 reproducible CI cycles with test outcomes, flakiness, durations, history, and seeded fault injections. `load_public_ci_csv(path_or_url)` accepts public/local CSV with required columns `cycle_id,test_id,duration,failed`. It derives missing history fields and defaults unavailable diff/flaky features to zero. Dataset versions are content hashes for CSV sources or seed/config hashes for simulation.

## Train and evaluate

```powershell
python -m pip install -r envs/requirements.txt
python -m envs.train_rl --seed 42 --timesteps 20000 --output-dir rl_outputs
python -m envs.eval_rl --seed 42 --models-dir rl_outputs/models --output-dir rl_outputs/evaluation
```

Training saves PPO/DQN models, reward-per-episode CSV/PNG learning curves, and a JSON manifest. Evaluation uses the final chronological 20% of CI cycles and writes `rl_evaluation.csv` plus a chart for NAPFD, time to first failure, and canary rollback ratio. Time to first failure is averaged over episodes that actually detect a CI fault or observe a canary SLO violation; it is blank when no episode fails. The CI baselines are random ordering and failed-newest-first. Canary policies are also compared with random-action and risk-aware rules. Evaluation explicitly supplies human approval for simulated deployment episodes so policies can be compared on rollout choices; the no-approval gate is checked separately in unit tests.

Run tests with:

```powershell
python -m pytest envs/tests -q
```
