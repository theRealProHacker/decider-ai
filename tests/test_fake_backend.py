from dataclasses import dataclass

import pytest

from decider.backend import BASE, Backend, ModelRef
from decider.backend.fake import FakeBackend, FakeBackendError
from decider.tasks import TaskSpec

TASK = TaskSpec("route", "Which team?", {"billing": "Money", "support": "Help", "sales": "Buy"})


@dataclass
class Ex:
    text: str
    label: str


def test_is_a_backend():
    backend: Backend = FakeBackend()
    assert backend.max_input(TASK) > 0


def test_base_predict_scores_every_label_deterministically():
    texts = ["my invoice is wrong", "the app crashes", "billing question"]
    first = FakeBackend().predict(BASE, TASK, texts)
    again = FakeBackend().predict(BASE, TASK, texts)
    assert first == again
    assert len(first) == 3
    for scores in first:
        assert set(scores) == set(TASK.labels)
    assert max(first[2], key=first[2].get) == "billing"  # keyword hit


def test_train_memorises_reports_progress_and_writes(tmp_path):
    backend = FakeBackend()
    seen = []
    examples = [Ex("the app crashes", "sales"), Ex("hello there", "billing")]
    ref = backend.train(BASE, TASK, examples, 7, tmp_path / "v1", seen.append)
    assert isinstance(ref, ModelRef) and ref != BASE
    assert seen and seen[-1] == 1.0 and seen == sorted(seen)
    assert any((tmp_path / "v1").iterdir())
    [scores] = backend.predict(ref, TASK, ["the app crashes"])
    assert max(scores, key=scores.get) == "sales"


def test_max_input_is_fixed_budget_of_whitespace_words():
    backend = FakeBackend(max_tokens=5)
    assert backend.max_input(TASK) == 5
    assert backend.count_tokens("one  two\nthree four\tfive") == 5


def test_can_fail_predict_for_a_model(tmp_path):
    backend = FakeBackend()
    ref = backend.train(BASE, TASK, [Ex("x", "sales")], 0, tmp_path, lambda p: None)
    backend.fail_predict(ref)
    with pytest.raises(FakeBackendError):
        backend.predict(ref, TASK, ["x"])
    backend.predict(BASE, TASK, ["x"])  # others still work
