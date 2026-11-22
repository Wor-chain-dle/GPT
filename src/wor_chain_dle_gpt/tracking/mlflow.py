import math
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

try:
    from mlflow import MlflowClient
    from mlflow.entities import Metric, Param
    from mlflow.exceptions import MlflowException
except ImportError as error:
    raise ImportError(
        "Install the MLflow adapter with uv sync --extra mlflow"
    ) from error

from .interfaces import Parameter


class MlflowRun:
    def __init__(self, client: MlflowClient, run_id: str):
        self._client = client
        self.run_id = run_id

    def log_params(self, params: Mapping[str, Parameter]) -> None:
        self._client.log_batch(
            self.run_id,
            params=[Param(key, str(value)) for key, value in params.items()],
        )

    def log_metrics(self, metrics: Mapping[str, float], *, step: int = 0) -> None:
        if not isinstance(step, int) or isinstance(step, bool) or step < 0:
            raise ValueError("Metric step must be a nonnegative integer")
        if any(not math.isfinite(value) for value in metrics.values()):
            raise ValueError("Metric values must be finite")
        timestamp = time.time_ns() // 1_000_000
        self._client.log_batch(
            self.run_id,
            metrics=[
                Metric(key, value, timestamp, step) for key, value in metrics.items()
            ],
        )

    def log_artifact(self, path: Path) -> None:
        if not path.is_file():
            raise ValueError("Artifact must be an existing file")
        self._client.log_artifact(self.run_id, str(path))


class MlflowTracker:
    def __init__(self, tracking_uri: str, experiment_name: str):
        self.client = MlflowClient(tracking_uri=tracking_uri)
        self.experiment_name = experiment_name

    def _experiment_id(self) -> str:
        experiment = self.client.get_experiment_by_name(self.experiment_name)
        if experiment is None:
            try:
                return self.client.create_experiment(self.experiment_name)
            except MlflowException as error:
                if error.error_code != "RESOURCE_ALREADY_EXISTS":
                    raise
                # Another process may have created the same experiment.
                experiment = self.client.get_experiment_by_name(self.experiment_name)
                if experiment is None:
                    raise
        if experiment.lifecycle_stage != "active":
            raise ValueError(
                "Configured experiment is deleted; restore it or choose another"
            )
        return experiment.experiment_id

    @contextmanager
    def run(
        self, name: str, *, tags: Mapping[str, str] | None = None
    ) -> Iterator[MlflowRun]:
        created = self.client.create_run(
            self._experiment_id(), run_name=name, tags=dict(tags or {})
        )
        run = MlflowRun(self.client, created.info.run_id)
        try:
            yield run
        except BaseException as error:
            status = (
                "KILLED"
                if isinstance(error, (KeyboardInterrupt, SystemExit))
                else "FAILED"
            )
            self.client.set_terminated(run.run_id, status=status)
            raise
        else:
            self.client.set_terminated(run.run_id, status="FINISHED")
