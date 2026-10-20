.PHONY: dev test eval eval-check

# Start the orchestrator without Docker (local mode: memory storage, in-process nodes).
dev:
	python -m uvicorn agents.app:app --reload --port 8000

# Run every module's tests.
test:
	python -m pytest agents/tests triage/tests rca/tests envs/tests -q

# One command creates a fresh timestamped result folder and runs the full harness.
eval:
	python -m eval.runner --config eval/config.json --output-root results

# Re-run the evaluation elsewhere and check it still matches the run the report cites.
eval-check:
	python -m eval.runner --config eval/config.json --output-root .eval-check
	python -m eval.compare_runs results/20260930T020846305626 $$(ls -d .eval-check/*/ | tail -1)
