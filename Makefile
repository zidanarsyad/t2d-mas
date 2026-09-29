.PHONY: eval

# One command creates a fresh timestamped result folder and runs the full harness.
eval:
	python -m eval.runner --config eval/config.json --output-root results
