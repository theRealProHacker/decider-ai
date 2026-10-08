"""``Decider``: the product as plain method calls (see docs/architecture.md)."""

from __future__ import annotations

import json
import logging
import math
import random
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Protocol

from decider import evaluation
from decider.backend import BASE, Backend, ModelRef
from decider.runner import Runner, ThreadRunner
from decider.store import Store
from decider.tasks import ConfigError, TaskSpec

Clock = Callable[[], float]
JobId = str

MIN_SPLIT_SIZE = 100  # examples in the frozen split
SPLIT_AT = 150  # confirmed examples before the split may freeze
MIN_TRAIN = 50  # confirmed non-split examples a retrain needs


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
    below_minimum: list[str] = field(default_factory=list)  # frozen-split labels under the minimum


@dataclass(frozen=True)
class Job:
    id: JobId
    task: str
    state: Literal["running", "succeeded", "failed"]
    progress: float
    epoch: int | None  # epochs done, when the backend reports epochs
    epochs: int | None  # total epochs, when the backend reports epochs
    verdict: str | None  # recommended | not_recommended | unverified, once succeeded
    metrics: dict[str, Any]
    version: str | None
    error: str | None


@dataclass(frozen=True)
class ModelVersion:
    version: str
    task: str
    verdict: str
    metrics: dict[str, Any]
    split_revision: int | None
    split_size: int | None
    erased: int  # examples it was trained on that were later forgotten
    active: bool
    seed: int
    created_at: float


@dataclass(frozen=True)
class Activation:
    warning: str | None


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


@dataclass(frozen=True)
class JobFinished:
    job_id: str
    task: str
    state: str
    version: str | None
    verdict: str | None


@dataclass(frozen=True)
class Activated:
    task: str
    version: str


Event = Decided | Confirmed | Erased | JobFinished | Activated


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
        runner: Runner | None = None,
        clock: Clock = time.time,
        events: Events = LogEvents(),
    ) -> None:
        self.tasks = {t.name: t for t in tasks}
        self.backend = backend
        self.runner = runner if runner is not None else ThreadRunner()
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
            self._recover_orphaned_jobs()
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

    # --- retrain, jobs, models, activate --------------------------------------

    def _recover_orphaned_jobs(self) -> None:
        """A job still 'running' at startup was cut off by a restart: mark it failed."""
        db = self.store.db
        for job_id, task in db.execute("SELECT id, task FROM jobs WHERE state='running'").fetchall():
            shutil.rmtree(self.model_dir / task / job_id, ignore_errors=True)
            db.execute(
                "UPDATE jobs SET state='failed', error='interrupted by restart', finished_at=? "
                "WHERE id=?",
                (self.clock(), job_id),
            )

    def _examples(self, task: str) -> list[Example]:
        rows = self.store.db.execute(
            "SELECT text, label, external_id, group_id, label_mode FROM examples "
            "WHERE task=? ORDER BY id",
            (task,),
        )
        return [Example(task, t, lbl, eid, gid, mode) for t, lbl, eid, gid, mode in rows]

    def _split(self, task: str) -> tuple[int, set[str]] | None:
        """The current frozen split: (revision, member external IDs), or None."""
        row = self.store.db.execute(
            "SELECT MAX(revision) FROM splits WHERE task=?", (task,)
        ).fetchone()
        if row[0] is None:
            return None
        members = self.store.db.execute(
            "SELECT external_id FROM split_members WHERE task=? AND revision=?", (task, row[0])
        )
        return row[0], {r[0] for r in members}

    def retrain(self, task: str, *, refresh_split: bool = False) -> JobId:
        spec = self._task(task)
        with self._lock:
            db = self.store.db
            running = db.execute("SELECT id FROM jobs WHERE state='running'").fetchone()
            if running:
                raise Busy(running[0])
            examples = self._examples(task)
            current = self._split(task)
            drawn: list[str] | None = None
            if (current is None or refresh_split) and len(examples) >= SPLIT_AT:
                result = evaluation.split(
                    examples, MIN_SPLIT_SIZE, min_per_label(len(spec.labels)),
                    prefer_blind=True, seed=random.randrange(2**31),
                )
                if isinstance(result, evaluation.Split):
                    drawn = [e.external_id for e in result.test]
            held = set(drawn) if drawn is not None else (current[1] if current else set())
            train = [e for e in examples if e.external_id not in held]
            if len(train) < MIN_TRAIN:
                raise TooFewExamples(len(train), MIN_TRAIN)

            job_id = uuid.uuid4().hex
            n = db.execute("SELECT COUNT(*) FROM model_versions WHERE task=?", (task,)).fetchone()
            version = f"{task}-v{n[0] + 1}"  # one job at a time, so this stays unique
            now = self.clock()
            revision = current[0] if current else None
            db.execute("BEGIN")
            try:
                if drawn is not None:
                    revision = (revision or 0) + 1
                    db.execute("INSERT INTO splits VALUES (?, ?, ?)", (task, revision, now))
                    db.executemany(
                        "INSERT INTO split_members VALUES (?, ?, ?)",
                        [(task, revision, eid) for eid in drawn],
                    )
                db.execute(
                    "INSERT INTO jobs (id, task, state, refresh_split, created_at) "
                    "VALUES (?, ?, 'running', ?, ?)",
                    (job_id, task, int(refresh_split), now),
                )
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
            split = (revision, [e for e in examples if e.external_id in held]) if held else None
        self.runner.start(
            lambda: self._run_job(job_id, version, spec, train, split, drawn is not None)
        )
        return job_id

    def _labels(self, model: ModelRef, spec: TaskSpec, texts: list[str]) -> list[str]:
        return [max(s, key=s.get) for s in self.backend.predict(model, spec, texts)]

    def _active_ref(self, spec: TaskSpec) -> ModelRef | None:
        with self._lock:
            active = self.store.active_version(spec.name)
        if active is not None:
            return ModelRef(active[0], Path(active[1]) if active[1] else None)
        return BASE if spec.zero_shot else None

    def _run_job(
        self,
        job_id: str,
        version: str,
        spec: TaskSpec,
        train: list[Example],
        split: tuple[int, list[Example]] | None,
        new_split: bool,
    ) -> None:
        out_dir = self.model_dir / spec.name / job_id
        db = self.store.db
        try:
            seed = random.randrange(2**31)  # product retrains use a random, recorded seed

            def progress(
                p: float, *, epoch: int | None = None, epochs: int | None = None
            ) -> None:
                with self._lock:
                    db.execute(
                        "UPDATE jobs SET progress=?, epoch=COALESCE(?, epoch), "
                        "epochs=COALESCE(?, epochs) WHERE id=?",
                        (min(p, 0.99), epoch, epochs, job_id),
                    )

            trained = self.backend.train(BASE, spec, train, seed, out_dir, progress)
            candidate = ModelRef(version, trained.path or out_dir)

            metrics: dict[str, Any] = {}
            comparison = None
            active = None
            reevaluation = None
            if split is not None:
                revision, held = split
                gold = [e.label for e in held]
                texts = [e.text for e in held]
                groups = [e.group_id or e.external_id for e in held]
                cand = self._labels(candidate, spec, texts)
                metrics.update(
                    split_revision=revision, split_size=len(held),
                    macro_f1=evaluation.macro_f1(gold, cand),
                )
                active = self._active_ref(spec)
                if active is not None:
                    act = self._labels(active, spec, texts)
                    comparison = evaluation.compare(gold, cand, [act], groups, seed=seed)
                    metrics.update(
                        compared_to=active.version,
                        active_macro_f1=evaluation.macro_f1(gold, act),
                        delta=comparison.delta, ci_low=comparison.ci_low,
                        ci_high=comparison.ci_high,
                    )
                    if new_split:  # a new split re-evaluates the active model too
                        reevaluation = {
                            "split_revision": revision, "split_size": len(held),
                            "macro_f1": metrics["active_macro_f1"],
                        }
                        metrics["active_reevaluation"] = {"version": active.version, **reevaluation}
            verdict = {
                evaluation.Recommended: "recommended",
                evaluation.NotRecommended: "not_recommended",
                evaluation.Unverified: "unverified",
            }[type(evaluation.recommend(comparison, split is not None))]

            with self._lock:
                db.execute("BEGIN")
                try:
                    db.execute(
                        "INSERT INTO model_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (version, spec.name, str(candidate.path), seed, self.clock(), verdict,
                         json.dumps(metrics), metrics.get("split_revision"),
                         metrics.get("split_size")),
                    )
                    db.executemany(
                        "INSERT OR IGNORE INTO version_examples (version, external_id) "
                        "VALUES (?, ?)",
                        [(version, e.external_id) for e in train],
                    )
                    # Anything forgotten while training already counts as erased.
                    db.execute(
                        "UPDATE version_examples SET erased=1 WHERE version=? AND external_id "
                        "NOT IN (SELECT external_id FROM examples WHERE task=?)",
                        (version, spec.name),
                    )
                    if reevaluation is not None and active is not None and active.path is not None:
                        row = db.execute(
                            "SELECT metrics FROM model_versions WHERE version=?", (active.version,)
                        ).fetchone()
                        old = json.loads(row[0] or "{}")
                        old.setdefault("reevaluations", []).append(reevaluation)
                        db.execute(
                            "UPDATE model_versions SET metrics=? WHERE version=?",
                            (json.dumps(old), active.version),
                        )
                    db.execute(
                        "UPDATE jobs SET state='succeeded', progress=1, version=?, finished_at=? "
                        "WHERE id=?",
                        (version, self.clock(), job_id),
                    )
                    db.execute("COMMIT")
                except BaseException:
                    db.execute("ROLLBACK")
                    raise
            self.events.emit(JobFinished(job_id, spec.name, "succeeded", version, verdict))
        except Exception as e:  # the job fails; serving is untouched
            shutil.rmtree(out_dir, ignore_errors=True)
            try:
                with self._lock:
                    db.execute(
                        "UPDATE jobs SET state='failed', error=?, finished_at=? WHERE id=?",
                        (type(e).__name__, self.clock(), job_id),
                    )
            except Exception:
                pass  # store closed: startup recovery marks the job failed
            self.events.emit(JobFinished(job_id, spec.name, "failed", None, None))

    def job(self, job_id: JobId) -> Job:
        with self._lock:
            row = self.store.db.execute(
                """SELECT j.id, j.task, j.state, j.progress, j.epoch, j.epochs, v.verdict, v.metrics,
                          j.version, j.error
                   FROM jobs j LEFT JOIN model_versions v ON v.version = j.version
                   WHERE j.id=?""",
                (job_id,),
            ).fetchone()
        if row is None:
            raise NotFound(f"job '{job_id}'")
        return Job(row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                   json.loads(row[7] or "{}"), row[8], row[9])

    def models(self, task: str) -> list[ModelVersion]:
        self._task(task)
        with self._lock:
            rows = self.store.db.execute(
                """SELECT v.version, v.verdict, v.metrics, v.split_revision, v.split_size,
                          (SELECT COALESCE(SUM(erased), 0) FROM version_examples e
                           WHERE e.version = v.version),
                          EXISTS (SELECT 1 FROM active a WHERE a.version = v.version),
                          v.seed, v.created_at
                   FROM model_versions v WHERE v.task=? ORDER BY v.rowid""",
                (task,),
            ).fetchall()
        return [
            ModelVersion(r[0], task, r[1], json.loads(r[2] or "{}"), r[3], r[4], r[5],
                         bool(r[6]), r[7], r[8])
            for r in rows
        ]

    def activate(self, task: str, version: str) -> Activation:
        """Atomic swap: load the version, one smoke prediction, flip the active pointer.

        The ``Backend`` port loads models on use and has no unload, so the old model
        is released by the backend once nothing asks for it.
        """
        spec = self._task(task)
        with self._lock:
            row = self.store.db.execute(
                """SELECT path, verdict, (SELECT COALESCE(SUM(erased), 0) FROM version_examples e
                                          WHERE e.version = v.version)
                   FROM model_versions v WHERE version=? AND task=?""",
                (version, task),
            ).fetchone()
        if row is None:
            raise NotFound(f"model version '{version}' of task '{task}'")
        path, verdict, erased = row
        try:
            self.backend.predict(ModelRef(version, Path(path)), spec, ["smoke test"])
        except Exception as e:
            raise ActivationFailed(version, type(e).__name__) from e
        with self._lock:
            self.store.db.execute(
                "INSERT INTO active (task, version) VALUES (?, ?) "
                "ON CONFLICT (task) DO UPDATE SET version=excluded.version",
                (task, version),
            )
        self.events.emit(Activated(task, version))
        warnings = []
        if verdict == "unverified":
            warnings.append(f"{version} has no reliable evaluation (verdict unverified)")
        elif verdict == "not_recommended":
            warnings.append(f"{version} is not recommended: it did not clearly beat the model "
                            "that was active when it was trained")
        if erased:
            warnings.append(f"{erased} example(s) {version} was trained on were later erased")
        return Activation("; ".join(warnings) or None)

    def status(self) -> dict[str, TaskStatus]:
        out: dict[str, TaskStatus] = {}
        with self._lock:
            for name, spec in self.tasks.items():
                counts = self.store.label_counts(name)
                active = self.store.active_version(name)
                need = min_per_label(len(spec.labels))
                blocking = [lbl for lbl in spec.labels if counts.get(lbl, 0) < need]
                current = self._split(name)
                split: Pending | Frozen = Pending(blocking)
                below: list[str] = []
                if current is not None:
                    split = Frozen(current[0], len(current[1]))
                    split_labels = [
                        r[0]
                        for r in self.store.db.execute(
                            """SELECT e.label FROM split_members m JOIN examples e
                               ON e.task = m.task AND e.external_id = m.external_id
                               WHERE m.task=? AND m.revision=?""",
                            (name, current[0]),
                        )
                    ]
                    below = [lbl for lbl in spec.labels if split_labels.count(lbl) < need]
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
                    split=split,
                    unmeasured=serving == "base",
                    below_minimum=below,
                )
        return out

    def close(self) -> None:
        with self._lock:
            self.store.close()
