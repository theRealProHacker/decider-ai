"""The ``Backend`` port: the only true-external dependency (the model)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Protocol, Sequence

from decider.tasks import TaskSpec

if TYPE_CHECKING:
    from decider.core import Example


@dataclass(frozen=True)
class ModelRef:
    """Identifies a model a backend can load: ``base`` or a trained version."""

    version: str
    path: Path | None = None


BASE = ModelRef("base")


class Backend(Protocol):
    def predict(
        self, model: ModelRef, task: TaskSpec, texts: list[str]
    ) -> list[dict[str, float]]: ...

    def train(
        self,
        base: ModelRef,
        task: TaskSpec,
        examples: Sequence[Example],
        seed: int,
        out_dir: Path,
        progress: Callable[[float], None],
    ) -> ModelRef: ...

    def max_input(self, task: TaskSpec) -> int: ...

    def count_tokens(self, text: str) -> int: ...
