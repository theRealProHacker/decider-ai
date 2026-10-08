"""Deterministic in-memory test backend. Tokens are whitespace-separated words."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Sequence

from decider.backend import BASE, ModelRef
from decider.tasks import TaskSpec


class FakeBackendError(RuntimeError):
    pass


class FakeBackend:
    def __init__(self, max_tokens: int = 512) -> None:
        self.max_tokens = max_tokens
        # Trained models are identified by their directory, so a caller may name
        # them freely; a model written by another instance is reloaded from disk.
        self._memory: dict[str, dict[str, str]] = {"base": {}}
        self._failing: set[str] = set()
        self._trained = 0

    def fail_predict(self, model: ModelRef) -> None:
        """Make every later ``predict`` on a model of this version raise ``FakeBackendError``."""
        self._failing.add(model.version)

    def _load(self, model: ModelRef) -> dict[str, str] | None:
        if model.path is None:
            return self._memory.get(model.version)
        key = str(model.path)
        if key not in self._memory:
            file = Path(model.path) / "fake_model.json"
            if not file.exists():
                return None
            self._memory[key] = json.loads(file.read_text())["memory"]
        return self._memory[key]

    @staticmethod
    def count_tokens(text: str) -> int:
        return len(text.split())

    def max_input(self, task: TaskSpec) -> int:
        return self.max_tokens

    def predict(
        self, model: ModelRef, task: TaskSpec, texts: list[str]
    ) -> list[dict[str, float]]:
        if model.version in self._failing:
            raise FakeBackendError(f"predict failed for {model.version}")
        memory = self._load(model)
        if memory is None:
            raise FakeBackendError(f"unknown model {model.version}")
        return [self._score(task, text, memory.get(text)) for text in texts]

    @staticmethod
    def _score(task: TaskSpec, text: str, memorised: str | None) -> dict[str, float]:
        words = set(text.lower().split())
        raw = {}
        for label in task.labels:
            digest = hashlib.sha256(f"{label}\0{text}".encode()).digest()
            raw[label] = 1.0 + digest[0] / 255  # deterministic noise in [1, 2]
            if label.lower() in words:  # keyword hit
                raw[label] += 5.0
            if label == memorised:
                raw[label] += 100.0
        total = sum(raw.values())
        return {label: v / total for label, v in raw.items()}

    def train(
        self,
        base: ModelRef,
        task: TaskSpec,
        examples: Sequence[Any],
        seed: int,
        out_dir: Path,
        progress: Callable[[float], None],
    ) -> ModelRef:
        memory = dict(self._load(base) or {})
        n = len(examples)
        for i, ex in enumerate(examples):
            memory[ex.text] = ex.label
            progress((i + 1) / (n + 1))
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "fake_model.json").write_text(
            json.dumps({"task": task.name, "seed": seed, "memory": memory})
        )
        self._trained += 1
        ref = ModelRef(f"fake-{self._trained}", out_dir)
        self._memory[str(out_dir)] = memory
        progress(1.0)
        return ref
