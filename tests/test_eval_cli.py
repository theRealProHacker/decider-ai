import json
import random
import time

import pytest

from decider import eval_cli, evaluation
from decider.backend.fake import FakeBackend

LABELS = ["billing", "support", "other"]
SECRET = "SECRETTEXT"
BUDGETS = [50, 250]
SEEDS = [0, 1]


class SlowFake(FakeBackend):
    """Fake with a measurable per-call latency so p95 comparisons are meaningful."""

    def predict(self, model, task, texts):
        time.sleep(0.002)
        return super().predict(model, task, texts)


def make_dataset(root, name, n_test=60, n_train=300):
    d = root / "data" / name
    (d / "subsets").mkdir(parents=True)
    rng = random.Random(name)
    recs = []
    for i in range(n_train):
        recs.append({"external_id": f"{name}-train-{i}", "text": f"{SECRET} train {i} {rng.random()}",
                     "label": LABELS[i % 3], "group_id": f"{name}-train-{i}", "label_mode": "assisted"})
    for i in range(n_test):
        recs.append({"external_id": f"{name}-test-{i}", "text": f"{SECRET} test {i} {rng.random()}",
                     "label": LABELS[i % 3], "group_id": f"{name}-test-{i}", "label_mode": "blind"})
    (d / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    train_ids = [r["external_id"] for r in recs if r["label_mode"] == "assisted"]
    for b in BUDGETS:
        for s in SEEDS:
            (d / "subsets" / f"{b}-{s}.json").write_text(json.dumps(random.Random(s).sample(train_ids, b)))
    tasks = root / "tasks"
    tasks.mkdir(exist_ok=True)
    (tasks / f"{name}.yaml").write_text(
        f"tasks:\n  - name: {name}\n    question: Which team?\n    labels:\n"
        + "".join(f"      {lab}: about {lab}\n" for lab in LABELS)
    )
    return [r for r in recs if r["label_mode"] == "blind"]


def write_system(root, ds, name, test, *, kind="local", zero_shot=False, correct=True, latency=1.0,
                 null_first=0, skip=None):
    p = root / "predictions" / ds
    p.mkdir(parents=True, exist_ok=True)
    keys = [(0, 0)] if zero_shot else [(b, s) for b in BUDGETS for s in SEEDS]
    lines = []
    for b, s in keys:
        if skip == (b, s):
            continue
        for i, r in enumerate(test):
            label = r["label"] if correct else "other"
            if i < null_first:
                label = None
            line = {"external_id": r["external_id"], "budget": b, "seed": s, "label": label, "latency_ms": latency}
            if kind == "api":
                line.update(input_tokens=0, output_tokens=0)
            lines.append(line)
    (p / f"{name}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    meta = {"kind": kind}
    if kind == "api":
        meta.update(model="gemini-test", settings={"temperature": 0}, price_input_per_million_usd=0.3,
                    price_output_per_million_usd=2.5, price_date="2026-10-08", training_seconds={"0/0": 0.0})
    else:
        meta["train_seconds"] = {f"{b}-{s}": 0.01 for b, s in keys}
    (p / f"{name}.meta.json").write_text(json.dumps(meta))


def run(root, datasets, backend=None, extra=()):
    logs = []
    argv = ["--data-dir", str(root / "data"), "--datasets", ",".join(datasets),
            "--tasks-dir", str(root / "tasks"), "--predictions", str(root / "predictions"),
            "--budgets", ",".join(map(str, BUDGETS)), "--seeds", "0-1", "--machine", "test box",
            "--fx", "0.9,2026-10-08", "--resamples", "200", "--out", str(root / "out"), *extra]
    report = eval_cli.run(argv, backend=backend or FakeBackend(), log=logs.append)
    return report, "\n".join(logs)


def names(report, i=0):
    return [s["name"] for s in report["datasets"][i]["systems"]]


def test_writes_json_and_markdown_rendered_from_json_only(tmp_path):
    make_dataset(tmp_path, "ds1")
    report, _ = run(tmp_path, ["ds1"])
    on_disk = json.loads((tmp_path / "out" / "report.json").read_text())
    assert on_disk["schema_version"] == eval_cli.SCHEMA_VERSION
    md = (tmp_path / "out" / "report.md").read_text()
    assert eval_cli.render_md(on_disk) == md
    assert "ds1" in md and "Learning curve" in md


def test_systems_come_from_prediction_files_not_hard_coded(tmp_path):
    test = make_dataset(tmp_path, "ds1")
    report, _ = run(tmp_path, ["ds1"])
    assert names(report) == ["finetune", "zero_shot"]
    assert report["gate"]["outcome"] is None
    write_system(tmp_path, "ds1", "foo", test)
    report, _ = run(tmp_path, ["ds1"])
    assert names(report) == ["finetune", "zero_shot", "foo"]
    foo = report["datasets"][0]["systems"][2]
    assert [r["budget"] for r in foo["rows"]] == BUDGETS
    assert foo["rows"][0]["macro_f1"] == 1.0
    assert [v["finetune_budget"] for v in foo["vs_finetune"]] == BUDGETS


def test_missing_budget_seed_names_file_and_budget(tmp_path):
    test = make_dataset(tmp_path, "ds1")
    write_system(tmp_path, "ds1", "foo", test, skip=(250, 1))
    with pytest.raises(eval_cli.EvalError, match=r"foo\.jsonl: no predictions for budget 250 seed 1"):
        run(tmp_path, ["ds1"])


def test_gate_rescope_when_llm_wins_everywhere_launch_when_one_slower(tmp_path):
    tests = {ds: make_dataset(tmp_path, ds) for ds in ("ds1", "ds2")}
    for ds, test in tests.items():
        write_system(tmp_path, ds, "llm", test, kind="api", zero_shot=True, latency=0.001)
    report, _ = run(tmp_path, ["ds1", "ds2"], backend=SlowFake())
    assert report["gate"]["outcome"] == "ReScope"
    assert all(x["llm_wins"] for x in report["gate"]["per_dataset"])
    assert "**ReScope**" in (tmp_path / "out" / "report.md").read_text()

    write_system(tmp_path, "ds2", "llm", tests["ds2"], kind="api", zero_shot=True, latency=10_000)
    report, _ = run(tmp_path, ["ds1", "ds2"], backend=SlowFake())
    assert report["gate"]["outcome"] == "Launch"
    ds2 = report["gate"]["per_dataset"][1]
    assert (ds2["llm_faster"], ds2["llm_wins"]) == (False, False)


def test_invalid_llm_label_counts_as_wrong_and_is_reported(tmp_path):
    test = make_dataset(tmp_path, "ds1")
    write_system(tmp_path, "ds1", "llm", test, kind="api", zero_shot=True, null_first=6)
    report, _ = run(tmp_path, ["ds1"])
    llm = report["datasets"][0]["systems"][2]
    assert llm["rows"][0]["invalid"] == 6
    assert llm["rows"][0]["macro_f1"] < 1.0
    assert "| llm | zero-shot (vs 50) | " in (tmp_path / "out" / "report.md").read_text()
    assert "| 6 |" in (tmp_path / "out" / "report.md").read_text()


def test_zero_shot_rule_against_tfidf_at_50(tmp_path):
    test = make_dataset(tmp_path, "ds1")
    write_system(tmp_path, "ds1", "tfidf_lr", test, correct=False)  # always "other": weak
    report, _ = run(tmp_path, ["ds1"])
    rule = report["zero_shot_rule"]
    assert rule["per_dataset"][0]["baseline_f1"] == report["datasets"][0]["systems"][2]["rows"][0]["macro_f1"]
    assert rule["outcome"] == (rule["per_dataset"][0]["zero_shot_f1"] >= rule["per_dataset"][0]["baseline_f1"])


def test_no_message_text_in_outputs(tmp_path):
    test = make_dataset(tmp_path, "ds1")
    write_system(tmp_path, "ds1", "llm", test, kind="api", zero_shot=True)
    _, logs = run(tmp_path, ["ds1"])
    for text in [SECRET, *(r["text"] for r in test)]:
        assert text not in (tmp_path / "out" / "report.json").read_text()
        assert text not in (tmp_path / "out" / "report.md").read_text()
        assert text not in logs


def test_api_cost_uses_tokens_prices_and_fx(tmp_path):
    test = make_dataset(tmp_path, "ds1")
    write_system(tmp_path, "ds1", "llm", test, kind="api", zero_shot=True)
    p = tmp_path / "predictions" / "ds1" / "llm.jsonl"
    lines = [json.loads(x) for x in p.read_text().splitlines()]
    for x in lines:
        x.update(input_tokens=1000, output_tokens=10)
    p.write_text("".join(json.dumps(x) + "\n" for x in lines))
    report, _ = run(tmp_path, ["ds1"])
    row = report["datasets"][0]["systems"][2]["rows"][0]
    expected = 1000 * 0.9 * (1000 * 0.3 + 10 * 2.5) / 1e6
    assert row["cost_per_1k"] == pytest.approx(expected)
    assert row["cost_per_1k_high"] == pytest.approx(expected * 1.3)


def test_paired_bootstrap_matches_evaluation_compare():
    rng = random.Random(1)
    gold = [rng.choice(LABELS) for _ in range(40)]
    a = [g if rng.random() < 0.8 else rng.choice(LABELS) for g in gold]
    bs = [[rng.choice(LABELS) for _ in gold] for _ in range(3)]
    groups = [i // 2 for i in range(40)]
    ref = evaluation.compare(gold, a, bs, groups, resamples=300, seed=0)
    got = eval_cli.paired_bootstrap(gold, [a], bs, groups, resamples=300, seed=0)
    assert got.n == ref.n
    for f in ("delta", "ci_low", "ci_high"):
        assert getattr(got, f) == pytest.approx(getattr(ref, f))
