import json
from pathlib import Path

import pytest

from wor_chain_dle_gpt.tracking import load_tracker
from wor_chain_dle_gpt.tracking.check import main
from wor_chain_dle_gpt.tracking.mlflow import MlflowTracker


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    # Opt in only for isolated tests; real configuration requires HTTP(S).
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")
    return MlflowTracker((tmp_path / "store").as_uri(), "isolated-test")


@pytest.mark.parametrize(
    "overrides",
    [
        {"EXPERIMENT_BACKEND": ""},
        {"EXPERIMENT_BACKEND": "unsupported"},
        {"EXPERIMENT_NAME": " "},
        {"MLFLOW_TRACKING_URI": ""},
        {"MLFLOW_TRACKING_URI": "file:///tmp/mlruns"},
        {"MLFLOW_TRACKING_URI": "https://user:private-password@example.com"},
        {"MLFLOW_TRACKING_URI": "https://example.com?token=private-token"},
        {"MLFLOW_TRACKING_URI": "https://[invalid"},
        {"MLFLOW_TRACKING_URI": "https://example.com:bad-port"},
    ],
)
def test_invalid_configuration_does_not_expose_credentials(overrides):
    values = {
        "EXPERIMENT_BACKEND": "mlflow",
        "EXPERIMENT_NAME": "test",
        "MLFLOW_TRACKING_URI": "https://mlflow.example.com",
        **overrides,
    }
    with pytest.raises(ValueError) as error:
        load_tracker(values)
    assert "private-password" not in str(error.value)
    assert "private-token" not in str(error.value)


def test_configuration_uses_supplied_server_without_changing_global_uri(monkeypatch):
    import mlflow

    before = mlflow.get_tracking_uri()
    tracker = load_tracker(
        {
            "EXPERIMENT_BACKEND": "mlflow",
            "EXPERIMENT_NAME": "chosen-experiment",
            "MLFLOW_TRACKING_URI": "https://mlflow.example.com/base",
        }
    )
    assert tracker.client.tracking_uri == "https://mlflow.example.com/base"
    assert tracker.experiment_name == "chosen-experiment"
    assert mlflow.get_tracking_uri() == before


def test_run_round_trips_params_metric_steps_and_artifact(tracker, tmp_path):
    artifact = tmp_path / "result.json"
    artifact.write_text('{"test": true}\n')
    with tracker.run("first", tags={"kind": "test"}) as run:
        run.log_params({"seed": 123, "enabled": True})
        run.log_metrics({"check": 0.0}, step=0)
        run.log_metrics({"check": 1.0}, step=1)
        run.log_artifact(artifact)
    saved = tracker.client.get_run(run.run_id)
    assert saved.info.status == "FINISHED"
    assert saved.data.params == {"seed": "123", "enabled": "True"}
    assert saved.data.tags["kind"] == "test"
    assert [
        (m.step, m.value)
        for m in tracker.client.get_metric_history(run.run_id, "check")
    ] == [
        (0, 0.0),
        (1, 1.0),
    ]
    downloaded = tracker.client.download_artifacts(run.run_id, "result.json")
    assert Path(downloaded).read_text() == artifact.read_text()
    with tracker.run("second") as other:
        assert other.run_id != run.run_id
    assert len(tracker.client.search_runs([saved.info.experiment_id])) == 2


@pytest.mark.parametrize(
    "error,status", [(RuntimeError, "FAILED"), (KeyboardInterrupt, "KILLED")]
)
def test_exception_marks_run_and_propagates(tracker, error, status):
    with pytest.raises(error):
        with tracker.run("failure") as run:
            raise error("intentional test")
    assert tracker.client.get_run(run.run_id).info.status == status


def test_invalid_metrics_and_missing_artifact_do_not_write(tracker, tmp_path):
    with tracker.run("invalid") as run:
        for step in [-1, True, 0.5]:
            with pytest.raises(ValueError):
                run.log_metrics({"check": 1.0}, step=step)
        for value in [float("nan"), float("inf")]:
            with pytest.raises(ValueError):
                run.log_metrics({"check": value})
        with pytest.raises(ValueError):
            run.log_artifact(tmp_path / "missing")
    assert tracker.client.get_run(run.run_id).data.metrics == {}


def test_deleted_experiment_is_not_recreated(tracker):
    with tracker.run("first") as run:
        pass
    experiment = tracker.client.get_run(run.run_id).info.experiment_id
    tracker.client.delete_experiment(experiment)
    with pytest.raises(ValueError, match="deleted"):
        with tracker.run("must-not-start"):
            pytest.fail("Deleted experiment must reject new runs")


def test_connection_check_reads_back_artifact_and_does_not_log_env(
    tracker, monkeypatch, capsys
):
    monkeypatch.setattr(
        "wor_chain_dle_gpt.tracking.check.load_tracker", lambda: tracker
    )
    monkeypatch.setenv("MLFLOW_TRACKING_TOKEN", "private-token")
    main()
    output = json.loads(capsys.readouterr().out)
    assert output["readback"] == "passed"
    saved = tracker.client.get_run(output["run_id"])
    assert saved.data.tags["run_kind"] == "connection-check"
    assert "private-token" not in json.dumps(saved.to_dictionary())
