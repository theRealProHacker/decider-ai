import dataclasses
import logging
import threading

import pytest

from decider.backend.fake import FakeBackend
from decider.core import (
    Decider,
    DeciderError,
    Example,
    Forgotten,
    InputTooLong,
    NotFound,
    NotTrained,
    Pending,
    RecordedEvents,
    UnknownTask,
)
from decider.tasks import ConfigError, TaskSpec

LABELS = {"billing": "Money", "support": "Help", "sales": "Buy"}
ZS = TaskSpec("zs", "Which team?", LABELS, max_input_tokens=5, zero_shot=True)
NZ = TaskSpec("nz", "Which team?", LABELS)
SENTINEL = "zqxsentinel4711"


@pytest.fixture
def env(tmp_path):
    made = []

    def make(tasks=(ZS, NZ), backend=None):
        events = RecordedEvents()
        d = Decider(
            list(tasks),
            backend=backend or FakeBackend(max_tokens=20),
            db_path=tmp_path / "decider.db",
            model_dir=tmp_path / "models",
            events=events,
        )
        made.append(d)
        return d, events

    make.db = tmp_path / "decider.db"
    yield make
    for d in made:
        try:
            d.close()
        except Exception:
            pass


def stored_bytes(db):
    data = db.read_bytes()
    wal = db.with_name(db.name + "-wal")
    if wal.exists():
        data += wal.read_bytes()
    return data


def ex(external_id, label="billing", text="hello there", task="zs", **kw):
    return Example(task=task, text=text, label=label, external_id=external_id, **kw)


def test_cold_start_zero_shot_serves_base(env):
    d, _ = env()
    a = d.decide("zs", "my invoice is wrong")
    b = d.decide("zs", "my invoice is wrong")
    assert a.model_version == "base"
    assert set(a.predictions) == set(LABELS)
    assert a.request_id and a.request_id != b.request_id


def test_cold_start_not_zero_shot_raises_not_trained(env):
    d, _ = env()
    with pytest.raises(NotTrained) as e:
        d.decide("nz", "hi")
    assert e.value.code == "MODEL_NOT_TRAINED"


def test_unknown_task(env):
    d, _ = env()
    with pytest.raises(UnknownTask) as e:
        d.decide("nope", "hi")
    assert e.value.code == "TASK_NOT_FOUND"
    assert isinstance(e.value, DeciderError)


def test_never_truncate_task_limit(env):
    d, _ = env()  # task limit 5, backend 20
    d.decide("zs", "one two three four five")
    with pytest.raises(InputTooLong) as e:
        d.decide("zs", "one two three four five six")
    assert e.value.code == "INPUT_TOO_LONG" and e.value.limit == 5


def test_never_truncate_backend_limit_wins_when_smaller(env):
    d, _ = env(backend=FakeBackend(max_tokens=3))
    d.decide("zs", "one two three")
    with pytest.raises(InputTooLong) as e:
        d.decide("zs", "one two three four")
    assert e.value.limit == 3
    assert d.status()["zs"].input_limit == 3


def test_decide_stores_no_text(env):
    d, events = env()
    d.confirm([ex("e1")])  # make sure the db has pages written
    d.decide("zs", f"{SENTINEL} billing")
    assert SENTINEL.encode() not in stored_bytes(env.db)
    [decided] = [e for e in events.events if type(e).__name__ == "Decided"]
    assert {f.name for f in dataclasses.fields(decided)} == {"request_id", "task", "label", "scores"}
    assert SENTINEL not in repr(events.events)


def test_confirm_outcomes_in_order(env):
    d, _ = env()
    out = d.confirm(
        [
            ex("a", "billing"),
            ex("a", "support"),
            ex("b", "nope"),
            ex("c", task="missing"),
            ex("d", text="one two three four five six"),
            ex("e", "sales"),
        ]
    )
    assert [(o.index, o.kind, o.reason) for o in out] == [
        (0, "added", None),
        (1, "updated", None),
        (2, "rejected", "LABEL_NOT_IN_TASK"),
        (3, "rejected", "TASK_NOT_FOUND"),
        (4, "rejected", "INPUT_TOO_LONG"),
        (5, "added", None),
    ]
    assert d.status()["zs"].confirmed == 2
    # the upsert changed the stored label: forget then shows one example removed
    assert d.forget("a") == Forgotten(1, 0, [])


def test_upsert_changes_label(env):
    d, _ = env()
    d.confirm([ex(f"x{i}", "billing") for i in range(10)])
    assert "billing" not in d.status()["zs"].split.blocking_labels
    d.confirm([ex("x0", "support")])
    blocking = d.status()["zs"].split.blocking_labels
    assert "billing" in blocking  # 9 billing left after the label moved


def test_example_requires_external_id():
    with pytest.raises(TypeError):
        Example(task="zs", text="t", label="billing")  # type: ignore[call-arg]


def test_request_id_unknown_is_accepted(env):
    d, _ = env()
    dec = d.decide("zs", "hi")
    out = d.confirm([ex("a", request_id=dec.request_id), ex("b", request_id="never-served")])
    assert [o.kind for o in out] == ["added", "added"]
    assert b"never-served" in stored_bytes(env.db)


def test_status_cold(env):
    d, _ = env()
    d.confirm([ex("a", "billing")])
    st = d.status()
    zs, nz = st["zs"], st["nz"]
    assert (zs.serving, zs.unmeasured, zs.active_version, zs.confirmed) == ("base", True, None, 1)
    assert (nz.serving, nz.unmeasured, nz.active_version, nz.confirmed) == ("not_trained", False, None, 0)
    assert zs.input_limit == 5 and nz.input_limit == 20
    # min(10, 100 // 3) = 10 per label
    assert zs.split == Pending(["billing", "support", "sales"])


def test_pending_minimum_with_many_labels(env):
    labels = {f"l{i}": "x" for i in range(20)}  # min(10, 100 // 20) = 5
    t = TaskSpec("many", "q?", labels)
    d, _ = env(tasks=[t])
    d.confirm([ex(f"e{i}", "l0", task="many") for i in range(5)])
    d.confirm([ex(f"f{i}", "l1", task="many") for i in range(4)])
    blocking = d.status()["many"].split.blocking_labels
    assert "l0" not in blocking and "l1" in blocking and len(blocking) == 19


def test_forget(env):
    d, _ = env()
    secret = f"{SENTINEL} please forget me"
    d.confirm([ex("gone", text=secret), ex("gone", task="nz", text=secret), ex("keep")])
    assert SENTINEL.encode() in stored_bytes(env.db)
    f = d.forget("gone")
    assert f == Forgotten(examples_removed=2, split_members_removed=0, versions_trained_on=[])
    st = d.status()
    assert st["zs"].confirmed == 1 and st["nz"].confirmed == 0
    assert SENTINEL.encode() not in stored_bytes(env.db)
    with pytest.raises(NotFound) as e:
        d.forget("gone")
    assert e.value.code == "NOT_FOUND"


def test_no_text_in_events_or_logs(env, caplog):
    caplog.set_level(logging.DEBUG)
    d, events = env()
    text = f"{SENTINEL} billing"
    d.decide("zs", text)
    d.confirm([ex("s", text=text), ex("t", label="nope", text=text), ex("u", task="x", text=text)])
    d.forget("s")
    assert events.events
    for event in events.events:
        for f in dataclasses.fields(event):
            assert f.name != "text"
            assert SENTINEL not in repr(getattr(event, f.name))
    assert all(SENTINEL not in r.getMessage() for r in caplog.records)


def test_default_log_events_have_no_text(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    d = Decider([ZS], backend=FakeBackend(), db_path=tmp_path / "x.db", model_dir=tmp_path / "m")
    d.decide("zs", f"{SENTINEL} hi")
    d.confirm([ex("s", text=f"{SENTINEL} hi")])
    d.forget("s")
    d.close()
    assert caplog.records  # LogEvents did log
    assert all(SENTINEL not in r.getMessage() for r in caplog.records)


def test_label_set_change_refuses_startup(env):
    d, _ = env()
    d.confirm([ex("a")])
    d.close()
    changed = TaskSpec("zs", "Which team?", {**LABELS, "legal": "Law"}, zero_shot=True)
    with pytest.raises(ConfigError) as e:
        env(tasks=[changed, NZ])
    assert "zs" in str(e.value) and "new task name" in str(e.value)


def test_description_change_starts_and_removed_task_keeps_data(env):
    d, _ = env()
    d.confirm([ex("a"), ex("b", task="nz")])
    d.close()
    redescribed = TaskSpec("zs", "Which team?", {k: v + "!" for k, v in LABELS.items()}, zero_shot=True)
    d2, _ = env(tasks=[redescribed])  # nz removed
    assert set(d2.status()) == {"zs"}
    d2.close()
    d3, _ = env()  # nz back
    assert d3.status()["nz"].confirmed == 1


def test_restart_keeps_examples(env):
    d, _ = env()
    d.confirm([ex(f"e{i}") for i in range(7)])
    d.close()
    d2, _ = env()
    assert d2.status()["zs"].confirmed == 7


def test_thread_safe(env):
    d, _ = env()
    errors = []
    calls_per_thread = 25  # 8 * 25 = 200 calls

    def work(t):
        try:
            for i in range(calls_per_thread):
                if i % 2:
                    d.decide("zs", f"message {t} {i}")
                else:
                    [o] = d.confirm([ex(f"t{t}-{i}", text=f"message {t} {i}")])
                    assert o.kind == "added"
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=work, args=(t,)) for t in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert not errors
    assert d.status()["zs"].confirmed == 8 * 13
