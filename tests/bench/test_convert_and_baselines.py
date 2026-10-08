import json
from pathlib import Path

import pytest
import yaml

pytest.importorskip("sklearn")  # bench dependency group

import baselines  # noqa: E402
import convert  # noqa: E402

TASKS = Path(__file__).resolve().parents[2] / "bench" / "tasks"


@pytest.mark.parametrize("name,n", [("massive_de_scenario.yaml", 18), ("clinc_domain.yaml", 11)])
def test_task_yaml_has_labels_with_descriptions(name, n):
    tasks = yaml.safe_load((TASKS / name).read_text(encoding="utf-8"))["tasks"]
    assert len(tasks) == 1
    t = tasks[0]
    assert t["question"] and t["zero_shot"] is False and t["max_input_tokens"] > 0
    assert len(t["labels"]) == n and all(isinstance(d, str) and d for d in t["labels"].values())


def test_massive_records(tmp_path):
    p = tmp_path / "m.jsonl"
    rows = [
        {"id": "1", "partition": "train", "scenario": "alarm", "utt": "a"},
        {"id": "2", "partition": "dev", "scenario": "alarm", "utt": "b"},
        {"id": "3", "partition": "test", "scenario": "iot", "utt": "c"},
    ]
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert convert.convert_massive(p) == [
        {"external_id": "massive-de-DE-1", "text": "a", "label": "alarm", "group_id": "massive-de-DE-1", "label_mode": "assisted"},
        {"external_id": "massive-de-DE-3", "text": "c", "label": "iot", "group_id": "massive-de-DE-3", "label_mode": "blind"},
    ]


def test_clinc_records(tmp_path):
    data = {
        "train": [["t0", "pay_bill"]], "oos_train": [["t1", "oos"]],
        "val": [["v", "pay_bill"]], "oos_val": [],
        "test": [["x0", "weather"]], "oos_test": [["x1", "oos"]],
    }
    (tmp_path / "d.json").write_text(json.dumps(data))
    (tmp_path / "dom.json").write_text(json.dumps({"banking": ["pay_bill"], "utility": ["weather"]}))
    recs = convert.convert_clinc(tmp_path / "d.json", tmp_path / "dom.json")
    assert [(r["external_id"], r["label"], r["label_mode"]) for r in recs] == [
        ("clinc-train-0", "banking", "assisted"),
        ("clinc-train-1", "out_of_scope", "assisted"),
        ("clinc-test-0", "utility", "blind"),
        ("clinc-test-1", "out_of_scope", "blind"),
    ]


def _records(n_labels=4, per_label=30, test_per_label=5):
    recs = []
    for k in range(n_labels):
        for i in range(per_label):
            recs.append(convert.record(f"tr-{k}-{i}", f"label{k} word{k} sample {i}", f"l{k}", "train"))
        for i in range(test_per_label):
            recs.append(convert.record(f"te-{k}-{i}", f"label{k} word{k} probe {i}", f"l{k}", "test"))
    return recs


def test_subsets_cover_labels_have_budget_and_are_deterministic():
    train = [r for r in _records() if r["label_mode"] == "assisted"]
    train_ids = {r["external_id"] for r in train}
    label = {r["external_id"]: r["label"] for r in train}
    for budget in (4, 10, 50):
        for seed in range(5):
            ids = convert.subset(train, budget, seed)
            assert len(ids) == budget == len(set(ids))
            assert set(ids) <= train_ids
            assert {label[i] for i in ids} == {"l0", "l1", "l2", "l3"}
            assert ids == convert.subset(train, budget, seed)
    assert convert.subset(train, 10, 0) != convert.subset(train, 10, 1)
    assert len(convert.subset(train, "all", 0)) == len(train)
    with pytest.raises(ValueError):
        convert.subset(train, 3, 0)


def test_baselines_write_prediction_files(tmp_path):
    recs = _records()
    convert.write_dataset(recs, tmp_path / "data", [8, 12], [0, 1])
    scores = baselines.run_dataset(tmp_path / "data", tmp_path / "pred")
    n_test = sum(r["label_mode"] == "blind" for r in recs)
    for system in ("majority", "tfidf_lr"):
        lines = [json.loads(x) for x in (tmp_path / "pred" / f"{system}.jsonl").read_text().splitlines()]
        assert len(lines) == n_test * 4
        assert {(x["budget"], x["seed"]) for x in lines} == {(8, 0), (8, 1), (12, 0), (12, 1)}
        assert all(set(x) == {"external_id", "budget", "seed", "label", "latency_ms"} for x in lines)
        assert all(x["latency_ms"] >= 0 for x in lines)
        meta = json.loads((tmp_path / "pred" / f"{system}.meta.json").read_text())
        assert meta["kind"] == "local" and set(meta["train_seconds"]) == {"8-0", "8-1", "12-0", "12-1"}
    assert scores["tfidf_lr"][12][0] == pytest.approx(1.0)  # trivially separable synthetic set


def test_majority_breaks_ties_by_sorted_label():
    assert baselines.Majority().fit(["a", "b", "c"], ["z", "b", "z"]).predict(["x"]) == ["z"]
    assert baselines.Majority().fit(["a", "b"], ["z", "b"]).predict(["x"]) == ["b"]
