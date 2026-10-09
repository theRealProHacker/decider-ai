"""LayaBackend on the real pinned checkpoint. Slow: run with ``pytest -m laya -s``.

Training data: ``data/massive_de_scenario/records.jsonl`` (T1.2), or the file named by
``DECIDER_MASSIVE_RECORDS``.
"""

from __future__ import annotations

import json
import os
import resource
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.laya

ROOT = Path(__file__).resolve().parents[1]
RECORDS = Path(
    os.environ.get("DECIDER_MASSIVE_RECORDS", ROOT / "data" / "massive_de_scenario" / "records.jsonl")
)


@pytest.fixture(scope="module")
def backend():
    from decider.backend.laya import LayaBackend

    return LayaBackend(epochs=1)  # 1 epoch keeps the training test short


@pytest.fixture(scope="module")
def task():
    from decider.tasks import load

    return load(ROOT / "bench" / "tasks" / "massive_de_scenario.yaml")[0]


def _peak_rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2


def test_predict_base_scores_every_label(backend, task):
    from decider.backend import BASE

    texts = [
        "weck mich morgen um sieben uhr",
        "wie wird das wetter am wochenende in berlin",
        "spiel etwas von den beatles",
    ]
    start = time.perf_counter()
    scores = backend.predict(BASE, task, texts)
    print(f"\npredict 3 texts (incl. load): {time.perf_counter() - start:.1f}s")
    assert len(scores) == 3
    for s in scores:
        assert set(s) == set(task.labels)
        assert sum(s.values()) == pytest.approx(1.0, abs=0.01)
    print("argmax:", [max(s, key=s.get) for s in scores])


def test_task_too_long_for_head_is_rejected(backend):
    from decider.backend import BASE
    from decider.tasks import ConfigError, TaskSpec

    labels = {f"label_{i}": "eine sehr lange Beschreibung mit vielen Wörtern " * 2 for i in range(18)}
    long_task = TaskSpec("too_long", "Worum geht es?", labels)
    with pytest.raises(ConfigError, match="too_long"):
        backend.max_input(long_task)
    with pytest.raises(ConfigError):
        backend.predict(BASE, long_task, ["hallo"])


def test_max_input_is_exact_room(backend, task):
    from decider.backend import BASE

    head = backend.head_tokens(task)
    limit = backend.max_input(task)
    print(f"\nquestion+options: {head} tokens, max_input: {limit}")
    assert head <= 240
    assert limit == 1024 - head - 4  # [CLS] [SEP] ... [SEP] state [SEP]
    at_limit = " ".join(["haus"] * limit)
    assert backend.count_tokens(at_limit) == limit
    assert backend.count_tokens(at_limit + " haus") == limit + 1
    long_text = "Das ist ein sehr langer Text über das Wetter. " * 200
    assert backend.count_tokens(long_text) > limit
    (scores,) = backend.predict(BASE, task, [at_limit])  # a text at the limit is served
    assert set(scores) == set(task.labels)


@pytest.mark.skipif(not RECORDS.exists(), reason=f"{RECORDS} missing (run bench/fetch.py)")
def test_train_learns_training_labels(backend, task, tmp_path):
    by_label = defaultdict(list)
    for line in RECORDS.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["label_mode"] == "assisted" and len(by_label[r["label"]]) < 3:
            by_label[r["label"]].append(SimpleNamespace(text=r["text"], label=r["label"]))
    examples = [ex for exs in by_label.values() for ex in exs]
    assert len(examples) == 54

    seen = []
    epochs_seen = []
    start = time.perf_counter()
    from decider.backend import BASE

    ref = backend.train(BASE, task, examples, seed=0, out_dir=tmp_path / "v1", progress=lambda p, **kw: (seen.append(p), epochs_seen.append(kw)))
    took = time.perf_counter() - start
    print(f"\ntrain {len(examples)} examples, 1 epoch: {took:.1f}s, peak RSS {_peak_rss_gb():.2f} GB")

    assert seen[0] == 0.0 and seen[-1] == 1.0 and seen == sorted(seen)
    assert {"epoch": 1, "epochs": 1} in epochs_seen
    assert (ref.path / "model.safetensors").exists()
    assert not (ref.path / "checkpoint_latest").exists()

    scores = backend.predict(ref, task, [ex.text for ex in examples])
    acc = sum(max(s, key=s.get) == ex.label for s, ex in zip(scores, examples)) / len(examples)
    print(f"training-label accuracy after training: {acc:.2f} (chance {1 / 18:.2f})")
    assert acc > 1 / 18
