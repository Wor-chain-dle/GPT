import json
from pathlib import Path

import pytest

from wor_chain_dle_gpt.environment import GameEnvironment
from wor_chain_dle_gpt.experiments import RandomPolicy, run_episode, run_experiment
from wor_chain_dle_gpt.tracking.mlflow import MlflowTracker


def submit(environment, word, mode):
    if mode == "word":
        return environment.step({"type": "submit", "word": word})
    # Read the actual lock from the engine instead of duplicating chain rules.
    locked = environment._state.observation["input"]["lockedIndex"]
    for index, letter in enumerate(word):
        if index != locked:
            environment.step({"type": "type", "letter": letter})
    return environment.step({"type": "enter"})


def test_installed_package_reset_hidden_answer_and_cleanup():
    with GameEnvironment() as env:
        with pytest.raises(RuntimeError, match="reset"):
            env.step({"type": "enter"})
        initial = env.reset(solution="prior")
        assert "solution" not in json.dumps(initial.observation)
        assert env.versions["engineVersion"] == "0.1.0"
        assert len(env.answers) == env.dictionary_metadata["answers"]["count"]
        initial.observation["status"] = "won"
        initial.stats["actionCount"] = 1000
        response = env.step({"type": "enter"})
        assert response.feedback == {"code": "word_incomplete"}
        assert response.observation["status"] == "playing"
        assert response.stats["actionCount"] == 1
    assert env._client.closed
    assert env._client.returncode is not None


def test_key_editing_error_recovery_and_actual_counters():
    with GameEnvironment() as env:
        env.reset(solution="prior")
        for letter in "priox":
            env.step({"type": "type", "letter": letter})
        invalid = env.step({"type": "enter"})
        assert invalid.feedback["code"] == "word_not_found"
        assert invalid.observation["guessCount"] == 0
        assert invalid.observation["input"]["editableText"] == "priox"
        env.step({"type": "backspace"})
        env.step({"type": "type", "letter": "r"})
        win = env.step({"type": "enter"})
        assert win.terminated and not win.truncated
        assert win.observation["endReason"] == "win"
        assert win.stats["lettersTyped"] == 6
        assert win.stats["backspacePresses"] == 1
        assert win.stats["directSubmissions"] == 0
        with pytest.raises(RuntimeError, match="finished"):
            env.step({"type": "enter"})


@pytest.mark.parametrize(
    "words,ending",
    [
        (["crane"], "win"),
        (["stale", "blaze", "boost", "first", "flood"], "dead_end"),
        (["stale", "blaze", "boost", "first", "forge", "pride"], "guess_limit"),
        (["stale", "blaze", "boost", "first", "forge", "crane"], "win"),
    ],
)
def test_word_and_key_modes_preserve_every_turn_and_termination(words, ending):
    histories = []
    for mode in ("word", "key"):
        observations = []
        with GameEnvironment() as env:
            env.reset(solution="crane")
            for word in words:
                state = submit(env, word, mode)
                assert state.accepted
                observations.append(state.observation)
            assert state.terminated and not state.truncated
            assert state.observation["endReason"] == ending
            assert state.observation["guessCount"] == len(words)
        histories.append(observations)
    assert histories[0] == histories[1]


def test_rejections_are_bounded_without_inventing_game_loss():
    with GameEnvironment(max_actions=2) as env:
        env.reset(solution="crane")
        assert not env.step({"type": "enter"}).done
        state = env.step({"type": "enter"})
        assert state.truncated and not state.terminated
        assert state.observation["status"] == "playing"
        assert state.observation["endReason"] is None
        assert state.observation["guessCount"] == 0
        assert state.stats["rejectedActions"] == 2
        with pytest.raises(RuntimeError, match="finished"):
            env.step({"type": "enter"})
        assert not env.reset(seed=123).done


def test_engine_termination_wins_over_action_budget():
    with GameEnvironment(max_actions=6) as env:
        env.reset(solution="crane")
        state = submit(env, "crane", "key")
        assert state.terminated and not state.truncated


def test_failed_reset_preserves_existing_episode():
    with GameEnvironment() as env:
        env.reset(solution="crane")
        env.step({"type": "type", "letter": "c"})
        with pytest.raises(Exception, match="invalid_solution"):
            env.reset(solution="zzzzz")
        state = env.step({"type": "type", "letter": "r"})
        assert state.observation["input"]["editableText"] == "cr"
        assert state.stats["actionCount"] == 2


def test_seeded_episodes_repeat_and_policy_receives_only_public_observations():
    with GameEnvironment() as env:
        results = []
        for _ in range(2):
            policy = RandomPolicy(env.allowed_words, seed=47, mode="key")
            results.append(run_episode(env, policy, seed=123))
        assert results[0] == results[1]
        assert "solution" not in json.dumps(results[0])
        received = []

        def policy(observation):
            assert "seed" not in observation
            assert "stats" not in observation
            received.append(observation["guessCount"])
            observation["status"] = "won"  # Mutating a view cannot end the engine game.
            return {"type": "enter"}

        env.max_actions = 2
        result = run_episode(env, policy, seed=123)
        assert received == [0, 0]
        assert result["truncated"]


@pytest.mark.parametrize("budget", [0, -1, True, 1.5])
def test_invalid_action_budget_is_rejected(budget):
    with pytest.raises(ValueError):
        GameEnvironment(max_actions=budget)


def test_missing_package_has_installation_guidance(tmp_path, monkeypatch):
    monkeypatch.setattr("wor_chain_dle_gpt.environment.ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="npm ci"):
        GameEnvironment()


def test_experiment_writes_reproducible_local_results_and_records_to_tracker(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")
    tracker = MlflowTracker((tmp_path / "tracking").as_uri(), "environment-test")
    options = dict(
        episodes=3, seed=42, mode="key", max_actions=128, output=tmp_path / "runs"
    )
    first = run_experiment(**options, tracker=tracker)
    second = run_experiment(**options)
    assert first != second
    assert (first / "episodes.jsonl").read_bytes() == (
        second / "episodes.jsonl"
    ).read_bytes()
    summary = json.loads((first / "summary.json").read_text())
    assert summary["episodes"] == 3
    assert sum(summary["endings"].values()) == 3
    assert summary["rejected_actions"] == 0
    run_id = json.loads((first / "tracking.json").read_text())["run_id"]
    saved = tracker.client.get_run(run_id)
    assert saved.info.status == "FINISHED"
    assert saved.data.params["engine.engineVersion"] == "0.1.0"
    downloaded = tracker.client.download_artifacts(run_id, "episodes.jsonl")
    assert Path(downloaded).read_bytes() == (first / "episodes.jsonl").read_bytes()


def test_tracking_failure_keeps_local_results(tmp_path):
    class BrokenTracker:
        def run(self, *_args, **_kwargs):
            raise ConnectionError("Test tracking server unavailable")

    with pytest.raises(ConnectionError):
        run_experiment(
            episodes=1,
            seed=7,
            mode="word",
            max_actions=1,
            output=tmp_path,
            tracker=BrokenTracker(),
        )
    folders = list(tmp_path.iterdir())
    assert len(folders) == 1
    assert (folders[0] / "summary.json").is_file()
    assert json.loads((folders[0] / "episodes.jsonl").read_text())["truncated"]
