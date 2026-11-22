"""Python episode boundary around the installed engine, without duplicated rules."""

import copy
import importlib.util
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

type Observation = dict[str, Any]
type Action = dict[str, Any]

ENGINE_VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parents[2]


def _engine_client(root: Path, node: str, timeout: float):
    """Load the reference client shipped in the package, not a sibling checkout."""
    try:
        manifest = json.loads((root / "package.json").read_text())
    except (OSError, ValueError) as error:
        raise RuntimeError(
            "Engine package missing; run npm ci in the GPT repository"
        ) from error
    if (
        manifest.get("name") != "@wor-chain-dle/engine"
        or manifest.get("version") != ENGINE_VERSION
    ):
        raise RuntimeError(
            f"Expected @wor-chain-dle/engine {ENGINE_VERSION}; run npm ci"
        )
    entry = root / "bin/wor-chain-dle-jsonl.mjs"
    package = root / "python/wor_chain_dle"
    if not entry.is_file() or not (root / "dist/index.js").is_file():
        raise RuntimeError("Installed engine has no compiled runtime; run npm ci")
    # Package-relative imports work without adding node_modules to sys.path.
    name = "_wcd_installed_engine_client"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(
            name, package / "__init__.py", submodule_search_locations=[str(package)]
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Installed engine has no Python client")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return module.EngineClient([node, str(entry)], timeout=timeout)


@dataclass(frozen=True)
class Transition:
    observation: Observation
    stats: dict[str, Any]
    accepted: bool | None
    feedback: dict[str, str] | None
    terminated: bool
    truncated: bool

    @property
    def done(self) -> bool:
        return self.terminated or self.truncated


class GameEnvironment:
    """One persistent engine process, reusable across bounded episodes.

    Rewards and token encodings are deliberately not defined. Policies receive
    only observations; reset and solution selection belong to the trusted runner.
    """

    def __init__(self, *, max_actions: int = 256, timeout: float = 10.0):
        if (
            isinstance(max_actions, bool)
            or not isinstance(max_actions, int)
            or max_actions < 1
        ):
            raise ValueError("max_actions must be a positive integer")
        self.max_actions = max_actions
        self._client = _engine_client(
            ROOT / "node_modules/@wor-chain-dle/engine",
            os.environ.get("WCD_NODE_EXECUTABLE", "node"),
            timeout,
        )
        self._state: Transition | None = None
        self._has_session = False
        self._actions = 0
        try:
            self.versions = copy.deepcopy(self._client.info)
            expected = {
                "engineVersion": ENGINE_VERSION,
                "jsonlProtocolVersion": "jsonl-v1",
                "inputProtocolVersion": "input-v1",
                "rulesVersion": "standard-v1",
            }
            if any(self.versions.get(key) != value for key, value in expected.items()):
                raise RuntimeError(
                    "Installed engine uses an unsupported version or protocol"
                )
            dictionary = self._client.dictionary()
            self.answers = tuple(dictionary["answers"])
            self.allowed_words = tuple(dictionary["allowedWords"])
            self.dictionary_metadata = copy.deepcopy(dictionary["metadata"])
        except BaseException:
            self._client.close()
            raise

    def _view(self, response: dict[str, Any]) -> Transition:
        terminated = response["observation"]["status"] != "playing"
        return Transition(
            observation=copy.deepcopy(response["observation"]),
            stats=copy.deepcopy(response["stats"]),
            accepted=response.get("accepted"),
            feedback=copy.deepcopy(response.get("feedback")),
            terminated=terminated,
            truncated=not terminated and self._actions >= self.max_actions,
        )

    def reset(self, *, seed: int = 0, solution: str | None = None) -> Transition:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("seed must be an integer")
        selected = (
            random.Random(seed).choice(self.answers) if solution is None else solution
        )
        operation = self._client.reset if self._has_session else self._client.create
        response = operation("episode", selected)
        self._has_session = True
        self._actions = 0
        self._state = self._view(response)
        return copy.deepcopy(self._state)

    def step(self, action: Action) -> Transition:
        if self._state is None:
            raise RuntimeError("Call reset before step")
        if self._state.done:
            raise RuntimeError("Episode finished; call reset before another action")
        response = self._client.act("episode", action)
        self._actions += 1
        self._state = self._view(response)
        return copy.deepcopy(self._state)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
