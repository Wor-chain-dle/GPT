from collections.abc import Mapping
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

type Parameter = str | int | float | bool


class ExperimentRun(Protocol):
    """A run owned by the configured tracking system."""

    @property
    def run_id(self) -> str: ...

    def log_params(self, params: Mapping[str, Parameter]) -> None: ...

    def log_metrics(self, metrics: Mapping[str, float], *, step: int = 0) -> None: ...

    def log_artifact(self, path: Path) -> None: ...


class ExperimentTracker(Protocol):
    def run(
        self, name: str, *, tags: Mapping[str, str] | None = None
    ) -> AbstractContextManager[ExperimentRun]: ...
