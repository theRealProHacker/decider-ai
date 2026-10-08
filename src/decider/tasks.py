"""Load ``tasks.yaml`` into validated ``TaskSpec``s.

File format::

    tasks:
      - name: route
        question: Which team should handle this message?
        labels:
          billing: Invoices, refunds and payment problems
          support: Product questions and bugs
        max_input_tokens: 512   # optional
        zero_shot: false        # optional, default false
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml


class ConfigError(Exception):
    """A configuration file is invalid. The message names the file and the reason."""


@dataclass(frozen=True)
class TaskSpec:
    name: str
    question: str
    labels: Mapping[str, str]  # label -> one-line description, in file order
    max_input_tokens: int | None = None
    zero_shot: bool = False

    @property
    def label_set_hash(self) -> str:
        """Hash over the sorted label names only (descriptions do not count)."""
        return hashlib.sha256("\n".join(sorted(self.labels)).encode()).hexdigest()


_TOP_KEYS = {"tasks"}
_TASK_KEYS = {"name", "question", "labels", "max_input_tokens", "zero_shot"}


def load(path: str | Path) -> list[TaskSpec]:
    path = Path(path)

    def fail(reason: str) -> ConfigError:
        return ConfigError(f"{path}: {reason}")

    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as e:
        raise fail(f"cannot read: {e}") from e

    if not isinstance(data, dict):
        raise fail("top level must be a mapping with a 'tasks' list")
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise fail(f"unknown top-level keys: {sorted(map(str, unknown))}")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise fail("'tasks' must be a non-empty list")

    specs: list[TaskSpec] = []
    seen: set[str] = set()
    for i, t in enumerate(tasks):
        if not isinstance(t, dict):
            raise fail(f"task #{i + 1} must be a mapping")
        name = t.get("name")
        if not isinstance(name, str) or not name.strip():
            raise fail(f"task #{i + 1}: missing 'name'")
        where = f"task '{name}'"
        unknown = set(t) - _TASK_KEYS
        if unknown:
            raise fail(f"{where}: unknown keys: {sorted(map(str, unknown))}")
        if name in seen:
            raise fail(f"duplicate task name '{name}'")
        seen.add(name)

        question = t.get("question")
        if not isinstance(question, str) or not question.strip():
            raise fail(f"{where}: missing 'question'")

        labels = t.get("labels")
        if not isinstance(labels, dict) or len(labels) < 2:
            raise fail(f"{where}: needs at least 2 labels")
        for label, desc in labels.items():
            if not isinstance(label, str) or not label.strip():
                raise fail(f"{where}: label names must be non-empty strings (quote yes/no/true/false)")
            if not isinstance(desc, str) or not desc.strip():
                raise fail(f"{where}: label '{label}' has no description")

        max_tokens = t.get("max_input_tokens")
        if max_tokens is not None and (
            isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0
        ):
            raise fail(f"{where}: 'max_input_tokens' must be a positive integer")

        zero_shot = t.get("zero_shot", False)
        if not isinstance(zero_shot, bool):
            raise fail(f"{where}: 'zero_shot' must be true or false")

        specs.append(
            TaskSpec(
                name=name,
                question=question,
                labels=MappingProxyType(dict(labels)),
                max_input_tokens=max_tokens,
                zero_shot=zero_shot,
            )
        )
    return specs
