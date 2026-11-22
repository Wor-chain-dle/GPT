"""Bounded episode execution and local results, independent of training frameworks."""

import argparse
import copy
import json
import random
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .environment import Action, GameEnvironment, Observation
from .tracking import ExperimentTracker, load_tracker

type Policy = Callable[[Observation], Action]


class RandomPolicy:
    """Diagnostic word sampler; key mode types a sampled word, not a learned policy."""

    def __init__(self, words: Sequence[str], *, seed: int, mode: str):
        if mode not in {"word", "key"}:
            raise ValueError("mode must be word or key")
        self._words = words
        self._rng = random.Random(seed)
        self._mode = mode
        self._turn = -1
        self._word = ""

    def __call__(self, observation: Observation) -> Action:
        if observation["guessCount"] != self._turn:
            chain = observation["chain"]
            candidates = self._words
            if chain:
                index = 0 if chain["position"] == "first" else -1
                candidates = [
                    word for word in candidates if word[index] == chain["letter"]
                ]
            self._word = self._rng.choice(candidates)
            self._turn = observation["guessCount"]
        if self._mode == "word":
            return {"type": "submit", "word": self._word}
        draft = observation["input"]
        editable = "".join(
            letter
            for index, letter in enumerate(self._word)
            if index != draft["lockedIndex"]
        )
        length = len(draft["editableText"])
        return (
            {"type": "type", "letter": editable[length]}
            if length < len(editable)
            else {"type": "enter"}
        )


def run_episode(environment: GameEnvironment, policy: Policy, *, seed: int) -> dict:
    state = environment.reset(seed=seed)
    initial = copy.deepcopy(state.observation)
    trajectory = []
    while not state.done:
        # A policy gets neither the environment object, selected answer, nor seed.
        action = policy(copy.deepcopy(state.observation))
        state = environment.step(action)
        trajectory.append({"action": copy.deepcopy(action), **asdict(state)})
    return {
        "seed": seed,
        "initial_observation": initial,
        "trajectory": trajectory,
        "guess_count": state.observation["guessCount"],
        "action_count": len(trajectory),
        "end_reason": state.observation["endReason"],
        "terminated": state.terminated,
        "truncated": state.truncated,
        "stats": state.stats,
    }


def run_experiment(
    *,
    episodes: int,
    seed: int,
    mode: str,
    max_actions: int,
    output: Path,
    tracker: ExperimentTracker | None = None,
) -> Path:
    if isinstance(episodes, bool) or not isinstance(episodes, int) or episodes < 1:
        raise ValueError("episodes must be a positive integer")
    if mode not in {"word", "key"}:
        raise ValueError("mode must be word or key")
    # A unique directory keeps previous runs intact, including when tracking fails.
    directory = output / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=False)
    metadata = {
        "run_kind": "environment-check",
        "policy": "random-legal-word-v1",
        "mode": mode,
        "episodes": episodes,
        "seed": seed,
        "max_actions": max_actions,
        "answer_selection": "python-random-choice-v1",
        "policy_seed": "episode-seed-xor-0x5A17",
        "python_version": sys.version.split()[0],
    }
    try:
        metadata["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        metadata["git_dirty"] = bool(
            subprocess.check_output(["git", "status", "--porcelain"], text=True)
        )
    except (OSError, subprocess.CalledProcessError):
        pass
    endings: Counter[str] = Counter()
    guesses = actions = rejected = 0
    with GameEnvironment(max_actions=max_actions) as environment:
        metadata["engine"] = environment.versions
        metadata["dictionary"] = environment.dictionary_metadata
        (directory / "config.json").write_text(json.dumps(metadata, indent=2) + "\n")
        with (directory / "episodes.jsonl").open("w") as stream:
            for index in range(episodes):
                episode_seed = seed + index
                policy = RandomPolicy(
                    environment.allowed_words, seed=episode_seed ^ 0x5A17, mode=mode
                )
                result = run_episode(environment, policy, seed=episode_seed)
                stream.write(json.dumps({"episode": index, **result}) + "\n")
                stream.flush()
                endings[
                    "truncated" if result["truncated"] else result["end_reason"]
                ] += 1
                guesses += result["guess_count"]
                actions += result["action_count"]
                rejected += result["stats"]["rejectedActions"]
    summary = {
        "episodes": episodes,
        "wins": endings["win"],
        "solve_rate": endings["win"] / episodes,
        "mean_guesses": guesses / episodes,
        "mean_actions": actions / episodes,
        "rejected_actions": rejected,
        "endings": dict(endings),
    }
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if tracker is not None:
        # Preserve local results regardless of remote logging availability.
        print(f"Local results: {directory}", file=sys.stderr)
        with tracker.run(
            "environment-check", tags={"run_kind": "environment-check"}
        ) as run:
            run.log_params(
                {
                    key: value
                    for key, value in metadata.items()
                    if isinstance(value, (str, int, float, bool))
                }
            )
            run.log_params(
                {
                    f"engine.{key}": value
                    for key, value in metadata["engine"].items()
                    if isinstance(value, str)
                }
            )
            run.log_metrics(
                {
                    key: float(value)
                    for key, value in summary.items()
                    if isinstance(value, (int, float))
                }
            )
            for filename in ("config.json", "episodes.jsonl", "summary.json"):
                run.log_artifact(directory / filename)
            (directory / "tracking.json").write_text(
                json.dumps({"run_id": run.run_id}) + "\n"
            )
    return directory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run bounded engine environment checks, not model training"
    )
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--mode", choices=["word", "key"], default="key")
    parser.add_argument("--max-actions", type=int, default=256)
    parser.add_argument("--output", type=Path, default=Path("runs"))
    parser.add_argument(
        "--track",
        action="store_true",
        help="Record through the configured experiment tracker",
    )
    args = parser.parse_args()
    if args.episodes < 1 or args.max_actions < 1:
        parser.error("--episodes and --max-actions must be positive")
    output = run_experiment(
        episodes=args.episodes,
        seed=args.seed,
        mode=args.mode,
        max_actions=args.max_actions,
        output=args.output,
        tracker=load_tracker() if args.track else None,
    )
    print(
        json.dumps(
            {
                "directory": str(output),
                "summary": json.loads((output / "summary.json").read_text()),
            }
        )
    )
