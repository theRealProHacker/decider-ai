"""``Decider``: the product as plain method calls (see docs/architecture.md)."""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Protocol

from decider.backend import BASE, Backend, ModelRef
from decider.store import Store
from decider.tasks import ConfigError, TaskSpec

Clock = Callable[[], float]

MIN_SPLIT_SIZE = 100


def min_per_label(n_labels: int) -> int:
    """Per-label minimum for the frozen split."""
    return min(10, MIN_SPLIT_SIZE // n_labels)


# --- errors ------------------------------------------------------------------


class DeciderError(Exception):
    """Every error ``Decider`` raises. ``code`` is stable; fields are structured."""

    code = "DECIDER_ERROR"


class UnknownTask(DeciderError):
    code = "TASK_NOT_FOUND"

    def __init__(self, task: str) -> None:
        self.task = task
        super().__init__(f"unknown task '{task}'")


class InputTooLong(DeciderError):
    code = "INPUT_TOO_LONG"

    def __init__(self, limit: int) -> None:
        self.limit = limit
        super().__init__(f"input is longer than {limit} tokens")


class NotTrained(DeciderError):
    code = "MODEL_NOT_TRAINED"

    def __init__(self, task: str) -> None:
        self.task = task
        super().__init__(f"task '{task}' has no active model; train and activate one first")


class NotFound(DeciderError):
    code = "NOT_FOUND"

    def __init__(self, what: str) -> None:
        self.what = what
        super().__init__(f"not found: {what}")


class Busy(DeciderError):  # T2.4
    code = "BUSY"

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"a retrain job is already running: {job_id}")


class TooFewExamples(DeciderError):  # T2.4
    code = "TOO_FEW_EXAMPLES"

    def __init__(self, have: int, need: int = 50) -> None:
        self.have, self.need = have, need
        super().__init__(f"retrain needs {need} confirmed examples, have {have}")


class ActivationFailed(DeciderError):  # T2.4
    code = "ACTIVATION_FAILED"

    def __init__(self, version: str, reason: str = "") -> None:
        self.version = version
        super().__init__(f"activating {version} failed{': ' + reason if reason else ''}")


# --- values ------------------------------------------------------------------


@dataclass(frozen=True)
class Example:
    task: str
    text: str
    label: str
    external_id: str
    group_id: str | None = None
    label_mode: Literal["blind", "assisted"] = "assisted"
    request_id: str | None = None


@dataclass(frozen=True)
class Decision:
    request_id: str
    model_version: str
    predictions: dict[str, float]


@dataclass(frozen=True)
class Outcome:
    index: int
    kind: Literal["added", "updated", "rejected"]
    reason: str | None = None  # a DeciderError code when rejected


@dataclass(frozen=True)
class Forgotten:
    examples_removed: int
    split_members_removed: int = 0
    versions_trained_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Pending:
    blocking_labels: list[str]


@dataclass(frozen=True)
class Frozen:
    revision: int
    size: int


@dataclass(frozen=True)
class TaskStatus:
    serving: Literal["base", "trained", "not_trained"]
    input_limit: int
    active_version: str | None
    confirmed: int
    split: Pending | Frozen
    unmeasured: bool  # serving the base model zero-shot, whose quality is unmeasured


# --- events (no event type has a text field) ---------------------------------


@dataclass(frozen=True)
class Decided:
    request_id: str
    task: str
    label: str
    scores: dict[str, float]


@dataclass(frozen=True)
class Confirmed:
    index: int
    task: str
    kind: str
    reason: str | None


@dataclass(frozen=True)
class Erased:
    examples_removed: int
    split_members_removed: int


Event = Decided | Confirmed | Erased


class Events(Protocol):
    def emit(self, event: Event) -> None: ...


class LogEvents:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.log = logger or logging.getLogger("decider")

    def emit(self, event: Event) -> None:
        self.log.info("%r", event)


class RecordedEvents:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._lock = threading.Lock()

    def emit(self, event: Event) -> None:
        with self._lock:
            self.events.append(event)


# --- Decider -----------------------------------------------------------------


class Decider:
    def __init__(
        self,
        tasks: list[TaskSpec],
        *,
        backend: Backend,
        db_path: str | Path,
        model_dir: Path,
        runner: Any = None,  # used from T2.4
        clock: Clock = time.time,
        events: Events = LogEvents(),
    ) -> None:
        self.tasks = {t.name: t for t in tasks}
        self.backend = backend
        self.runner = runner
        self.clock = clock
        self.events = events
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.store = Store(db_path)
        try:
            for t in tasks:
                stored = self.store.task_hash(t.name)
                if stored is not None and stored != t.label_set_hash:
                    raise ConfigError(
                        f"task '{t.name}': its label set changed since data was stored under "
                        f"this name; a task's labels are fixed, so choose a new task name"
                    )
                self.store.put_task(t.name, t.label_set_hash, list(t.labels))
        except BaseException:
            self.store.close()
            raise

    def _task(self, name: str) -> TaskSpec:
        task = self.tasks.get(name)
        if task is None:
            raise UnknownTask(name)
        return task

    def _limit(self, task: TaskSpec) -> int:
        return min(task.max_input_tokens or math.inf, self.backend.max_input(task))

    def _check_length(self, task: TaskSpec, text: str) -> None:
        limit = self._limit(task)
        if self.backend.count_tokens(text) > limit:
            raise InputTooLong(limit)

    def decide(self, task: str, text: str, *, external_id: str | None = None) -> Decision:
        spec = self._task(task)
        self._check_length(spec, text)
        with self._lock:
            active = self.store.active_version(task)
        if active is not None:
            model = ModelRef(active[0], Path(active[1]) if active[1] else None)
        elif spec.zero_shot:
            model = BASE
        else:
            raise NotTrained(task)
        [scores] = self.backend.predict(model, spec, [text])
        decision = Decision(uuid.uuid4().hex, model.version, scores)
        self.events.emit(Decided(decision.request_id, task, max(scores, key=scores.get), scores))
        return decision

    def confirm(self, items: Iterable[Example]) -> list[Outcome]:
        outcomes: list[Outcome] = []
        with self._lock:
            db = self.store.db
            db.execute("BEGIN")
            try:
                for i, ex in enumerate(items):
                    outcomes.append(self._confirm_one(i, ex))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return outcomes

    def _confirm_one(self, index: int, ex: Example) -> Outcome:
        def reject(reason: str) -> Outcome:
            self.events.emit(Confirmed(index, getattr(ex, "task", "?"), "rejected", reason))
            return Outcome(index, "rejected", reason)

        spec = self.tasks.get(ex.task)
        if spec is None:
            return reject(UnknownTask.code)
        if not ex.external_id or not isinstance(ex.external_id, str):
            return reject("VALIDATION_FAILED")
        if not isinstance(ex.text, str) or ex.label_mode not in ("blind", "assisted"):
            return reject("VALIDATION_FAILED")
        if ex.label not in spec.labels:
            return reject("LABEL_NOT_IN_TASK")
        try:
            self._check_length(spec, ex.text)
        except InputTooLong:
            return reject(InputTooLong.code)
        new = self.store.upsert_example(
            ex.task, ex.external_id, ex.text, ex.label, ex.group_id, ex.label_mode,
            ex.request_id, self.clock(),
        )
        kind = "added" if new else "updated"
        self.events.emit(Confirmed(index, ex.task, kind, None))
        return Outcome(index, kind)

    def forget(self, external_id: str) -> Forgotten:
        with self._lock:
            n, m, versions = self.store.forget(external_id)
        if n == 0:
            raise NotFound(f"example '{external_id}'")
        self.events.emit(Erased(n, m))
        return Forgotten(n, m, versions)

    def status(self) -> dict[str, TaskStatus]:
        out: dict[str, TaskStatus] = {}
        with self._lock:
            for name, spec in self.tasks.items():
                counts = self.store.label_counts(name)
                active = self.store.active_version(name)
                need = min_per_label(len(spec.labels))
                blocking = [lbl for lbl in spec.labels if counts.get(lbl, 0) < need]
                if active is not None:
                    serving = "trained"
                elif spec.zero_shot:
                    serving = "base"
                else:
                    serving = "not_trained"
                out[name] = TaskStatus(
                    serving=serving,
                    input_limit=self._limit(spec),
                    active_version=active[0] if active else None,
                    confirmed=sum(counts.values()),
                    split=Pending(blocking),
                    unmeasured=serving == "base",
                )
        return out

    def close(self) -> None:
        with self._lock:
            self.store.close()
