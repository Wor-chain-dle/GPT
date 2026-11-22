import json
import platform
import subprocess
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from .config import load_tracker


def main() -> None:
    tracker = load_tracker()
    payload = {
        "purpose": "tracking-connection-check",
        "python_version": platform.python_version(),
        "project_version": version("wor-chain-dle-gpt"),
    }
    tags = {"project": "Wor-chain-dle/GPT", "run_kind": "connection-check"}
    try:
        tags["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        tags["git_dirty"] = str(
            bool(subprocess.check_output(["git", "status", "--porcelain"], text=True))
        ).lower()
    except (OSError, subprocess.CalledProcessError):
        pass

    with TemporaryDirectory(prefix="wcd-tracking-") as directory:
        artifact = Path(directory) / "connection-check.json"
        artifact.write_text(json.dumps(payload, indent=2) + "\n")
        with tracker.run("connection-check", tags=tags) as run:
            run.log_params(payload)
            run.log_metrics({"tracking_check": 1.0}, step=0)
            run.log_artifact(artifact)

        # Readback is specific to the selected adapter, outside experiment callers.
        from .mlflow import MlflowTracker

        if not isinstance(tracker, MlflowTracker):
            raise ValueError("Readback check is not implemented for this adapter")
        stored = tracker.client.get_run(run.run_id)
        if stored.info.status != "FINISHED":
            raise RuntimeError("Run was not marked FINISHED")
        if stored.data.params != payload:
            raise RuntimeError("Logged parameters did not round-trip")
        if stored.data.metrics.get("tracking_check") != 1.0:
            raise RuntimeError("Logged metric did not round-trip")
        destination = Path(directory) / "download"
        destination.mkdir()
        downloaded = tracker.client.download_artifacts(
            run.run_id, artifact.name, str(destination)
        )
        if json.loads(Path(downloaded).read_text()) != payload:
            raise RuntimeError("Logged artifact did not round-trip")
    print(
        json.dumps({"run_id": run.run_id, "status": "FINISHED", "readback": "passed"})
    )
