# Wor🔗dle GPT

Build and train a model from scratch using the principles of large language models to solve Wor🔗dle.

## Development

Requires Node.js 22+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Python 3.12 and dependencies are managed by `.python-version` and `uv.lock`.

```bash
npm ci --ignore-scripts
uv sync --locked --extra mlflow
cp .env.example .env
```

Edit `.env` for your tracking server, experiment name, and authentication.

```bash
uv run --locked --extra mlflow --env-file .env wcd-check-tracking
```

This creates a `connection-check` run, logs parameters, a test metric, and a JSON
artifact, then downloads them to verify the round trip. It is a connection check,
not a training result. The run ID is printed on success.

## Experiment environment

Run repeatable episodes against the released engine package:

```bash
# Local results; no tracking server or GPU required.
uv run --locked wcd-run --episodes 10 --seed 123 --mode key
uv run --locked wcd-run --episodes 10 --seed 123 --mode word

# Optional recording through your configured tracker.
uv run --locked --extra mlflow --env-file .env wcd-run --episodes 10 --track
```

Each run saves `config.json`, `episodes.jsonl`, and `summary.json` in a unique
ignored `runs/` directory. The runner records engine/protocol/dictionary versions,
seeds, actions, feedback, and actual counters. Tracking failures preserve local
results and return an error.

This command uses a random legal-word sampler to check the environment. In key
mode it types the sampled word one character at a time. It is not a trained model
or an evaluation benchmark. Training hardware remains undecided.

Use `GameEnvironment.reset()` / `step(action)` to plug in another policy. Both
character actions and full-word submissions are supported. Observations exclude
the selected answer. Action-budget exhaustion is `truncated`, separate from an
engine win or loss. No reward function or token encoding is selected yet.
See [the environment interface](docs/ENVIRONMENT.md) for examples and semantics.

## Experiment tracking

Tracking callers use a backend-independent interface:

```python
from pathlib import Path
from wor_chain_dle_gpt.tracking import load_tracker

tracker = load_tracker()
with tracker.run("my-experiment", tags={"run_kind": "experiment"}) as run:
    run.log_params({"seed": 123})
    run.log_metrics({"completed_games": 10}, step=0)
    run.log_artifact(Path("results.json"))  # An existing result file.
```

The MLflow adapter is currently implemented. Other systems can implement the same
`ExperimentTracker` / `ExperimentRun` interfaces without changing experiment code.
No training framework or model architecture is selected yet.

| Variable | Purpose |
| --- | --- |
| `EXPERIMENT_BACKEND` | Adapter selection; currently `mlflow` |
| `EXPERIMENT_NAME` | Destination experiment |
| `MLFLOW_TRACKING_URI` | Any reachable HTTP(S) MLflow server |
| `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD` | Optional basic authentication |
| `MLFLOW_TRACKING_TOKEN` | Optional bearer token |

Connection settings and credentials belong in the ignored `.env` or the process
environment. `uv run --env-file .env` loads local settings; Python does not load a
file implicitly. Missing configuration is an error, with no automatic local store.

For GitHub Actions, inject connection/authentication values from repository or
environment Secrets into the same environment variables. Use Variables for
`EXPERIMENT_BACKEND` and `EXPERIMENT_NAME` if desired. The runner must be able to
reach the server; a private-network server may require a self-hosted runner.
Regular CI uses temporary local stores and does not connect to a tracking server
or require credentials.

## Checks

```bash
uv run --locked --extra mlflow ruff check .
uv run --locked --extra mlflow ruff format --check .
uv run --locked --extra mlflow pytest
```
