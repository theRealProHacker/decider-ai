import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench"))

import llm_baseline as lb  # noqa: E402

TASKS = """tasks:
  - name: toy_zs
    question: What is the message about?
    zero_shot: true
    labels:
      alarm: Setting or changing alarms
      weather: Asking about the weather
"""


def setup(tmp_path, n=4):
    tasks = tmp_path / "tasks.yaml"
    tasks.write_text(TASKS)
    recs = tmp_path / "records.jsonl"
    lines = [{"external_id": f"x-{i}", "text": f"msg {i}", "label": "alarm", "group_id": f"x-{i}",
              "label_mode": "blind"} for i in range(n)]
    lines.append({"external_id": "train-0", "text": "t", "label": "alarm", "group_id": "train-0",
                  "label_mode": "assisted"})
    recs.write_text("\n".join(json.dumps(r) for r in lines) + "\n")
    return recs, tasks


def stub(answers):
    calls = []

    def client(prompt, labels):
        calls.append(prompt)
        return lb.Reply(answers[len(calls) - 1], 300, 5)

    return client, calls


def read_preds(out):
    return [json.loads(l) for l in (out / "toy" / f"{lb.SYSTEM}.jsonl").read_text().splitlines()]


def test_writes_predictions_and_meta(tmp_path):
    recs, tasks = setup(tmp_path)
    client, calls = stub(["alarm", "weather", "alarm", "weather"])
    lb.run(recs, tasks, "toy", tmp_path / "pred", client=client)
    preds = read_preds(tmp_path / "pred")
    assert [p["external_id"] for p in preds] == ["x-0", "x-1", "x-2", "x-3"]  # test records only
    for p in preds:
        assert p["latency_ms"] >= 0 and p["input_tokens"] == 300 and p["output_tokens"] == 5
        assert p["budget"] == 0 and p["seed"] == 0
    assert preds[1]["label"] == "weather"
    meta = json.loads((tmp_path / "pred" / "toy" / f"{lb.SYSTEM}.meta.json").read_text())
    assert meta["kind"] == "api"
    assert meta["model"] == "gemini-3.5-flash-lite"
    assert meta["thinking_level"] and meta["temperature"] == 0
    assert len(meta["prompt_template_sha256"]) == 64
    assert meta["price_input_per_million_usd"] and meta["price_output_per_million_usd"]
    assert meta["price_date"] and meta["run_date"]
    assert "Asking about the weather" in calls[0] and "msg 0" in calls[0]


def test_invalid_reply_is_null_and_counted(tmp_path, capsys):
    recs, tasks = setup(tmp_path, n=2)
    client, _ = stub(["alarm", "I think it is about pizza"])
    summary = lb.run(recs, tasks, "toy", tmp_path / "pred", client=client)
    assert read_preds(tmp_path / "pred")[1]["label"] is None
    assert summary["invalid"] == 1
    out = capsys.readouterr().out
    assert "1 invalid" in out
    assert "msg 0" not in out  # never print message text


def test_resume_skips_written_records(tmp_path):
    recs, tasks = setup(tmp_path, n=4)

    def crashing(prompt, labels):
        if "msg 2" in prompt:
            raise KeyboardInterrupt
        return lb.Reply("alarm", 1, 1)

    try:
        lb.run(recs, tasks, "toy", tmp_path / "pred", client=crashing)
    except KeyboardInterrupt:
        pass
    assert len(read_preds(tmp_path / "pred")) == 2
    client, calls = stub(["weather", "weather"])
    summary = lb.run(recs, tasks, "toy", tmp_path / "pred", client=client)
    assert len(calls) == 2 and summary["skipped"] == 2
    assert [p["external_id"] for p in read_preds(tmp_path / "pred")] == ["x-0", "x-1", "x-2", "x-3"]


def test_limit(tmp_path):
    recs, tasks = setup(tmp_path, n=4)
    client, calls = stub(["alarm"] * 4)
    lb.run(recs, tasks, "toy", tmp_path / "pred", limit=2, client=client)
    assert len(calls) == 2


def test_product_never_imports_llm_client():
    pattern = re.compile(r"^\s*(import|from)\s+.*\bgenai\b", re.M)
    hits = [p for p in (ROOT / "src" / "decider").rglob("*.py") if pattern.search(p.read_text())]
    assert hits == []
