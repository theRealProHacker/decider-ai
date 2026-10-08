import os
import threading

import pytest

from decider.backend import ModelRef
from decider.backend.fake import FakeBackend
from decider.core import (
    ActivationFailed,
    Busy,
    Decider,
    Example,
    Frozen,
    NotFound,
    Pending,
    RecordedEvents,
    TooFewExamples,
)
from decider.runner import InlineRunner, ManualRunner, ThreadRunner
from decider.tasks import TaskSpec

LABELS = {"billing": "Money", "support": "Help", "sales": "Buy"}
NZ = TaskSpec("nz", "Which team?", LABELS)
ZS = TaskSpec("zs", "Which team?", LABELS, zero_shot=True)
DAY = 24 * 3600


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


class RecordingBackend(FakeBackend):
    def __init__(self) -> None:
        super().__init__(max_tokens=50)
        self.train_calls: list[list[str]] = []

    def train(self, base, task, examples, seed, out_dir, progress):
        self.train_calls.append([e.external_id for e in examples])
        return super().train(base, task, examples, seed, out_dir, progress)


@pytest.fixture
def env(tmp_path):
    made = []

    def make(runner=None, backend=None, tasks=(NZ, ZS), clock=None):
        d = Decider(
            list(tasks),
            backend=backend or FakeBackend(max_tokens=50),
            runner=runner or InlineRunner(),
            db_path=tmp_path / "decider.db",
            model_dir=tmp_path / "models",
            clock=clock or FakeClock(),
            events=RecordedEvents(),
        )
        made.append(d)
        return d

    make.model_dir = tmp_path / "models"
    yield make
    for d in made:
        try:
            d.close()
        except Exception:
            pass


def feed(d, task, n, start=0, labels=tuple(LABELS), **kw):
    """Confirm n examples with distinct texts, labels round-robin."""
    items = [
        Example(task, f"{task} message {i}", labels[i % len(labels)], f"{task}-{i}", **kw)
        for i in range(start, start + n)
    ]
    assert all(o.kind != "rejected" for o in d.confirm(items))


def only(d, task):
    [v] = d.models(task)
    return v


# --- minimum and no automation ------------------------------------------------


def test_too_few_examples(env):
    d = env()
    feed(d, "nz", 49)
    with pytest.raises(TooFewExamples) as e:
        d.retrain("nz")
    assert (e.value.have, e.value.need, e.value.code) == (49, 50, "TOO_FEW_EXAMPLES")


def test_nothing_retrains_or_activates_by_itself(env):
    clock = FakeClock()
    d = env(clock=clock)
    feed(d, "zs", 50)
    feed(d, "zs", 100, start=50)
    assert d.models("zs") == []
    clock.now += 30 * DAY
    assert d.models("zs") == []
    assert d.status()["zs"].active_version is None
    assert d.decide("zs", "hello").model_version == "base"

    d.retrain("zs")
    assert d.status()["zs"].active_version is None
    assert d.decide("zs", "hello").model_version == "base"
    clock.now += 30 * DAY
    assert d.status()["zs"].active_version is None


# --- one job at a time --------------------------------------------------------


def test_one_job_at_a_time(env):
    runner = ManualRunner()
    d = env(runner=runner)
    feed(d, "nz", 60)
    feed(d, "zs", 60)
    job_id = d.retrain("nz")
    for task in ("nz", "zs"):
        with pytest.raises(Busy) as e:
            d.retrain(task)
        assert e.value.job_id == job_id and e.value.code == "BUSY"
    job = d.job(job_id)
    assert job.state == "running" and 0 <= job.progress < 1
    assert d.decide("zs", "hello").model_version == "base"

    runner.release()
    assert d.job(job_id).state == "succeeded"
    second = d.retrain("zs")
    runner.release()
    assert d.job(second).state == "succeeded"


def test_job_progress_is_visible_while_running(env):
    runner = ManualRunner()
    d = env(runner=runner)
    feed(d, "nz", 60)
    job_id = d.retrain("nz")
    seen = []
    original = d.backend.train

    def train(*a, **kw):
        result = original(*a, **kw)
        seen.append(d.job(job_id))
        return result

    d.backend.train = train
    runner.release()
    assert seen[0].state == "running" and seen[0].progress > 0


def test_job_unknown_raises_not_found(env):
    with pytest.raises(NotFound):
        env().job("nope")


# --- below 150: unverified, manual activation ---------------------------------


def test_below_split_unverified_and_manual_activation(env):
    d = env()
    feed(d, "nz", 60)
    job = d.job(d.retrain("nz"))
    assert job.state == "succeeded" and job.verdict == "unverified"
    v = only(d, "nz")
    assert not v.active and v.verdict == "unverified" and v.version == job.version
    assert isinstance(v.seed, int)
    assert d.status()["nz"].serving == "not_trained"

    act = d.activate("nz", v.version)
    assert "no reliable evaluation" in act.warning
    assert d.decide("nz", "hello").model_version == v.version
    assert d.status()["nz"].serving == "trained"
    assert d.status()["nz"].active_version == v.version
    assert only(d, "nz").active


# --- frozen split and verdicts ------------------------------------------------


def test_first_model_with_frozen_split_not_zero_shot_is_unverified(env):
    d = env()
    feed(d, "nz", 160)
    job = d.job(d.retrain("nz"))
    assert isinstance(d.status()["nz"].split, Frozen)
    assert job.verdict == "unverified"


def test_first_model_zero_shot_compares_against_base(env):
    d = env()
    feed(d, "zs", 160)
    job = d.job(d.retrain("zs"))
    assert job.verdict in ("recommended", "not_recommended")
    assert job.metrics["compared_to"] == "base"


def test_frozen_split_verdict_records_ci_revision_and_size(env):
    d = env()
    feed(d, "zs", 160)
    assert isinstance(d.status()["zs"].split, Pending)
    job = d.job(d.retrain("zs"))
    assert d.status()["zs"].split == Frozen(revision=1, size=100)
    assert job.verdict in ("recommended", "not_recommended")
    m = job.metrics
    assert m["ci_low"] <= m["ci_high"]
    assert (m["split_revision"], m["split_size"]) == (1, 100)
    assert d.status()["zs"].active_version is None
    assert d.decide("zs", "hello").model_version == "base"


def test_split_never_reaches_train(env):
    backend = RecordingBackend()
    d = env(backend=backend)
    feed(d, "zs", 160)
    d.retrain("zs")
    feed(d, "zs", 20, start=160)
    d.retrain("zs")
    split = d._split("zs")[1]
    assert len(split) == 100
    assert len(backend.train_calls) == 2
    for call in backend.train_calls:
        assert not split & set(call)


def test_split_prefers_blind_examples(env):
    d = env()
    feed(d, "zs", 120, label_mode="blind")
    feed(d, "zs", 100, start=120, label_mode="assisted")
    d.retrain("zs")
    blind = {f"zs-{i}" for i in range(120)}
    assert d._split("zs")[1] <= blind


def test_rare_label_keeps_split_pending(env):
    d = env()
    feed(d, "zs", 160, labels=("billing", "support"))
    feed(d, "zs", 3, start=160, labels=("sales",))
    job = d.job(d.retrain("zs"))
    assert d.status()["zs"].split == Pending(blocking_labels=["sales"])
    assert job.verdict == "unverified"


# --- activation ---------------------------------------------------------------


def test_activating_not_recommended_warns(env):
    d = env()
    feed(d, "zs", 160)
    job = d.job(d.retrain("zs"))
    # FakeBackend scores unseen (split) texts like base, so delta is 0: not recommended.
    assert job.verdict == "not_recommended"
    act = d.activate("zs", job.version)
    assert "not recommended" in act.warning
    assert d.decide("zs", "hello").model_version == job.version


def test_rollback(env):
    d = env()
    feed(d, "nz", 60)
    v1 = d.job(d.retrain("nz")).version
    v2 = d.job(d.retrain("nz")).version
    d.activate("nz", v2)
    assert d.decide("nz", "hello").model_version == v2
    d.activate("nz", v1)
    assert d.decide("nz", "hello").model_version == v1
    assert [m.active for m in d.models("nz")] == [True, False]


def test_activate_unknown_or_foreign_version_not_found(env):
    d = env()
    feed(d, "zs", 60)
    v = d.job(d.retrain("zs")).version
    with pytest.raises(NotFound):
        d.activate("nz", "nope")
    with pytest.raises(NotFound):
        d.activate("nz", v)


def test_activation_failure_leaves_active_model(env):
    backend = FakeBackend(max_tokens=50)
    d = env(backend=backend)
    feed(d, "nz", 60)
    versions = [d.job(d.retrain("nz")).version for _ in range(3)]
    d.activate("nz", versions[1])
    backend.fail_predict(ModelRef(versions[2]))
    with pytest.raises(ActivationFailed) as e:
        d.activate("nz", versions[2])
    assert e.value.code == "ACTIVATION_FAILED"
    assert d.decide("nz", "hello").model_version == versions[1]
    assert d.status()["nz"].active_version == versions[1]


# --- erasure after training ---------------------------------------------------


def test_erasure_after_training(env):
    d = env()
    feed(d, "zs", 60)
    v1 = d.job(d.retrain("zs")).version
    feed(d, "zs", 100, start=60)
    job2 = d.job(d.retrain("zs"))
    split = d._split("zs")[1]
    victim = next(f"zs-{i}" for i in range(60) if f"zs-{i}" in split)
    before = {m.version: (m.verdict, m.metrics) for m in d.models("zs")}

    gone = d.forget(victim)
    assert gone.split_members_removed == 1
    assert gone.versions_trained_on == [v1]
    st = d.status()["zs"]
    assert st.split == Frozen(revision=1, size=99)
    models = {m.version: m for m in d.models("zs")}
    assert models[v1].erased == 1 and models[job2.version].erased == 0
    assert {v: (m.verdict, m.metrics) for v, m in models.items()} == before
    act = d.activate("zs", v1)
    assert "1 example(s)" in act.warning and "erased" in act.warning


def test_status_names_labels_below_minimum_after_erasure(env):
    d = env()
    feed(d, "zs", 160)
    d.retrain("zs")
    split = d._split("zs")[1]
    label_of = {f"zs-{i}": list(LABELS)[i % 3] for i in range(160)}
    sales = [eid for eid in split if label_of[eid] == "sales"]
    for eid in sales[: len(sales) - 9]:  # leave 9 < min 10
        d.forget(eid)
    st = d.status()["zs"]
    assert isinstance(st.split, Frozen)
    assert st.below_minimum == ["sales"]


# --- refresh_split ------------------------------------------------------------


def test_refresh_split_draws_new_split_and_reevaluates_active(env):
    d = env()
    feed(d, "zs", 200)
    v1 = d.job(d.retrain("zs")).version
    d.activate("zs", v1)
    first = d._split("zs")[1]
    job = d.job(d.retrain("zs", refresh_split=True))
    assert d.status()["zs"].split == Frozen(revision=2, size=100)
    assert d._split("zs")[1] != first
    models = {m.version: m for m in d.models("zs")}
    new = models[job.version]
    assert new.split_revision == 2 and new.split_size == 100
    assert new.metrics["active_reevaluation"]["version"] == v1
    assert models[v1].metrics["reevaluations"][0]["split_revision"] == 2
    assert models[v1].split_revision == 1  # its own verdict is not recomputed


def test_without_refresh_split_stays(env):
    d = env()
    feed(d, "zs", 200)
    d.retrain("zs")
    first = d._split("zs")
    d.retrain("zs")
    assert d._split("zs") == first


# --- restart ------------------------------------------------------------------


def test_restart_recovers_orphaned_job(env):
    runner = ManualRunner()
    d = env(runner=runner)
    feed(d, "nz", 60)
    job_id = d.retrain("nz")
    partial = env.model_dir / "nz" / job_id
    partial.mkdir(parents=True)
    (partial / "half.bin").write_bytes(b"x")
    d.close()

    d2 = env()
    assert d2.job(job_id).state == "failed"
    assert not partial.exists()
    assert d2.job(d2.retrain("nz")).state == "succeeded"


def test_restart_keeps_models_and_active(env):
    d = env()
    feed(d, "nz", 60)
    v1 = d.job(d.retrain("nz")).version
    d.job(d.retrain("nz"))
    d.activate("nz", v1)
    before = d.models("nz")
    d.close()
    d2 = env()
    assert d2.models("nz") == before
    assert d2.status()["nz"].active_version == v1
    assert d2.decide("nz", "hello").model_version == v1


# --- ThreadRunner -------------------------------------------------------------


def test_thread_runner_trains_in_background(env):
    gate = threading.Event()
    started = threading.Event()
    seen = {}

    class SlowBackend(FakeBackend):
        def train(self, *a, **kw):
            tid = threading.get_native_id()
            seen["nice"] = os.getpriority(os.PRIO_PROCESS, tid)
            started.set()
            gate.wait(5)
            return super().train(*a, **kw)

    runner = ThreadRunner()
    assert runner.threads == max(1, (os.cpu_count() or 2) // 2)
    d = env(runner=runner, backend=SlowBackend(max_tokens=50))
    feed(d, "zs", 60)
    job_id = d.retrain("zs")
    assert started.wait(5)
    assert d.job(job_id).state == "running"
    assert d.decide("zs", "hello").model_version == "base"  # serving during training
    gate.set()
    runner.join(5)
    assert d.job(job_id).state == "succeeded"
    assert seen["nice"] > os.getpriority(os.PRIO_PROCESS, threading.get_native_id())
