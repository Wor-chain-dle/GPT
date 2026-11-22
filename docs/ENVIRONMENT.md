# Experiment environment

Install the locked engine package and Python environment from the GPT repository:

```bash
npm ci --ignore-scripts
uv sync --locked --extra mlflow
```

The runtime uses `@wor-chain-dle/engine` v0.1.0 from its GitHub Release and the
reference Python client included in that package. A sibling engine checkout is
not required. The engine keeps game rules and input feedback in one implementation.
Set `WCD_NODE_EXECUTABLE` if `node` is not the executable to use.

## Interact with the environment

```python
from wor_chain_dle_gpt.environment import GameEnvironment

with GameEnvironment(max_actions=256) as env:
    state = env.reset(seed=123)
    state = env.step({"type": "enter"})
    print(state.feedback)  # {'code': 'word_incomplete'}
    state = env.step({"type": "type", "letter": "c"})
    state = env.step({"type": "backspace"})
    state = env.step({"type": "submit", "word": "crane"})
    print(state.observation, state.terminated, state.truncated)
```

Each transition contains:

| Field | Meaning |
| --- | --- |
| `observation` | Board, tile feedback, draft, chain lock, and game status |
| `feedback` | Engine feedback code; `None` immediately after reset |
| `accepted` | Whether the engine accepted the action; `None` after reset |
| `stats` | Actual action/submission counters |
| `terminated` | The engine declared a win or loss |
| `truncated` | The action budget expired while the game was still playing |
| `done` | Either termination or truncation |

Reset starts a new episode and clears counters. Every returned game-action
response, including a rejection, consumes one runner action. A win or loss on the
last permitted action takes precedence over truncation. Call reset before the
first step and after a finished episode. A reset rejected for an invalid solution preserves the current
episode. Transport failures propagate; there is no automatic action retry.

`reset(solution='crane')` is available for controlled fixtures. Only the trusted
runner chooses or reads solutions. Policies receive observations, never the
client, environment object, selected answer, or answer-selection seed. Returned
views are copies and cannot modify engine state. There is no reward field: reward
and model-specific token/feedback encoding remain future design choices.

## Run a policy

```python
from wor_chain_dle_gpt.environment import GameEnvironment
from wor_chain_dle_gpt.experiments import run_episode

with GameEnvironment(max_actions=3) as env:
    result = run_episode(env, lambda observation: {"type": "enter"}, seed=123)
    assert result["truncated"]
    assert result["guess_count"] == 0
```

A policy is a callable from public observation to one engine action. It can return
`type`, `backspace`, `enter`, or `submit` actions. Actions are passed through to the
engine; this layer does not repair invalid model output or mask available actions.

## Diagnostic runner and reproducibility

`wcd-run --episodes 10 --seed 123 --mode key` checks the environment with a random
legal-word sampler. `--mode word` submits the same sampled words directly. The key
sampler plans a word before typing it; it does not represent a trained character
agent. `--max-actions` bounds an episode; `--output` changes the results parent.

Episode `i` selects its answer with `random.Random(seed + i).choice(answers)`.
The diagnostic policy has a separate RNG seeded with `(seed + i) ^ 0x5A17`.
The ordered answer list and allowed words come from the installed engine.
Reproduce results with the same Python version, engine package, dictionaries,
configuration, and source revision. This answer policy is for experiments and
does not implement the web's Daily or Event schedule.

Each run creates a new directory without overwriting earlier results:

- `config.json`: configuration, Python/engine/protocol versions, dictionary content
  fingerprints, Git revision and dirty-worktree flag.
- `episodes.jsonl`: one record per episode with its seed, initial observation,
  action/feedback/observation trajectory, counters, and final outcome.
- `summary.json`: solve rate, average submitted guesses/actions across all episodes,
  rejected actions, and separate engine end-reason/truncation counts.
- `tracking.json`: the tracker run ID when optional recording succeeds.

Selected solutions are not serialized, but seeds and dictionaries let the trusted
runner reconstruct them. Do not feed complete result files or configuration into
a policy as its observation. This runner has no train/evaluation split and its
numbers are environment diagnostics, not evidence of model quality.

Add `--track` and load your `.env` to record through the generic tracker interface.
Server settings and credentials are not included in result metadata. Local runs
work without MLflow installed or reachable. A remote recording failure returns an
error and retains completed local artifacts for inspection.
