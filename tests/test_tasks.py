import textwrap

import pytest

from decider.tasks import ConfigError, TaskSpec, load

VALID = """
tasks:
  - name: route
    question: Which team?
    labels:
      billing: Money things
      support: Product help
    max_input_tokens: 256
  - name: urgent
    question: Is it urgent?
    labels:
      now: Needs action today
      later: Can wait
    zero_shot: true
"""


def write(tmp_path, text):
    p = tmp_path / "tasks.yaml"
    p.write_text(textwrap.dedent(text))
    return p


def test_valid_file_loads_two_tasks(tmp_path):
    specs = load(write(tmp_path, VALID))
    assert [s.name for s in specs] == ["route", "urgent"]
    route = specs[0]
    assert route.question == "Which team?"
    assert dict(route.labels) == {"billing": "Money things", "support": "Product help"}
    assert route.max_input_tokens == 256
    assert route.zero_shot is False
    assert specs[1].zero_shot is True
    assert specs[1].max_input_tokens is None


def task(**overrides):
    t = {
        "name": "t",
        "question": "Q?",
        "labels": {"a": "A desc", "b": "B desc"},
        "max_input_tokens": 10,
    }
    t.update(overrides)
    return {k: v for k, v in t.items() if v is not ...}


@pytest.mark.parametrize(
    "data, reason",
    [
        ({"tasks": [task(question=...)]}, "question"),
        ({"tasks": [task(labels={"a": "A desc"})]}, "at least 2 labels"),
        ({"tasks": [task(labels={"a": "A desc", "b": None}, zero_shot=True)]}, "zero_shot needs a description"),
        ({"tasks": [task(labels={"a": "A desc", "b": 3})]}, "description must be text"),
        ({"tasks": [task(), task()]}, "duplicate task name"),
        ({"tasks": [task(zero_shot="yes")]}, "zero_shot"),
        ({"tasks": [task(max_input_tokens=0)]}, "max_input_tokens"),
        ({"tasks": [task(max_input_tokens="10")]}, "max_input_tokens"),
        ({"tasks": [task(max_input_tokens=1.5)]}, "max_input_tokens"),
        ({"tasks": [task()], "extra": 1}, "unknown top-level keys"),
    ],
)
def test_invalid_files_raise_config_error(tmp_path, data, reason):
    import yaml

    p = tmp_path / "tasks.yaml"
    p.write_text(yaml.safe_dump(data))
    with pytest.raises(ConfigError) as e:
        load(p)
    assert str(p) in str(e.value)
    assert reason in str(e.value)


def test_max_input_tokens_is_optional(tmp_path):
    import yaml

    p = tmp_path / "tasks.yaml"
    p.write_text(yaml.safe_dump({"tasks": [task(max_input_tokens=...)]}))
    assert load(p)[0].max_input_tokens is None


def test_label_set_hash_ignores_descriptions():
    a = TaskSpec("t", "Q", {"a": "one", "b": "two"})
    b = TaskSpec("t", "Q", {"b": "changed", "a": "also changed"})
    c = TaskSpec("t", "Q", {"a": "one", "b": "two", "c": "three"})
    d = TaskSpec("t", "Q", {"a": "one", "c": "two"})
    assert a.label_set_hash == b.label_set_hash
    assert a.label_set_hash != c.label_set_hash
    assert a.label_set_hash != d.label_set_hash


def test_descriptions_optional_without_zero_shot(tmp_path):
    p = tmp_path / "tasks.yaml"
    p.write_text("tasks:\n  - name: t\n    question: Which queue?\n    labels:\n      billing:\n      tech: ''\n      sales: Buying things\n")
    [spec] = load(p)
    assert dict(spec.labels) == {"billing": "", "tech": "", "sales": "Buying things"}
