import os
from collections.abc import Mapping
from urllib.parse import urlsplit

from .interfaces import ExperimentTracker


def load_tracker(env: Mapping[str, str] | None = None) -> ExperimentTracker:
    """Resolve an explicitly configured adapter, never a local fallback store."""
    values = os.environ if env is None else env
    backend = values.get("EXPERIMENT_BACKEND", "").strip()
    if backend != "mlflow":
        raise ValueError(
            "Set EXPERIMENT_BACKEND=mlflow; other adapters are not implemented"
        )
    experiment = values.get("EXPERIMENT_NAME", "").strip()
    if not experiment:
        raise ValueError("Set EXPERIMENT_NAME")
    uri = values.get("MLFLOW_TRACKING_URI", "").strip()
    try:
        parsed = urlsplit(uri)
        valid = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        )
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(
            "Set MLFLOW_TRACKING_URI to an HTTP(S) server URL; "
            "provide credentials through MLflow authentication environment variables"
        )

    # Only the selected adapter imports its optional SDK.
    from .mlflow import MlflowTracker

    return MlflowTracker(uri, experiment)
