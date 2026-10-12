"""Zero-shot predictions from Verdict (ModernBERT + GLiClass, 151M) with its published weights.

    git clone https://github.com/Heman10x-NGU/Verdict-open-jev data/raw/Verdict-open-jev
    uv run --group bench --with gliclass --with pydantic python bench/verdict_zero_shot.py \\
        --dataset massive_en_scenario

Reads <data-dir>/<dataset>/records.jsonl (test = label_mode blind) and <tasks-dir>/<dataset>.yaml
(question and label descriptions), runs Verdict's own DecisionEngine one text at a time, and writes
    <out>/<dataset>/verdict-1.4.jsonl      one line per test record, budget 0 seed 0 (zero-shot)
    <out>/<dataset>/verdict-1.4.meta.json  kind "local"
The label is the most probable of the task's labels; Verdict's extra "insufficient evidence" option
is left out so every system answers every record; each line says whether it ranked first
("abstained") and gives the probability of the chosen label ("confidence").
Prints aggregate macro-F1 only.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import yaml
from sklearn.metrics import f1_score

MODEL = "heman10x/rlcd-modernbert-151m"
SYSTEM = "verdict-1.4"


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--tasks-dir", type=Path, default=Path("bench/tasks"))
    p.add_argument("--out", type=Path, default=Path("predictions"))
    p.add_argument("--dataset", default="massive_en_scenario")
    p.add_argument("--verdict-src", type=Path, default=Path("data/raw/Verdict-open-jev"))
    p.add_argument("--limit", type=int, default=0, help="smoke test: cap test records")
    args = p.parse_args(argv)

    sys.path.insert(0, str(args.verdict_src.resolve()))
    from core.engine_encoder import DecisionEngine  # Verdict's own inference code
    from core.primitives import Choice, Option

    task = yaml.safe_load((args.tasks_dir / f"{args.dataset}.yaml").read_text(encoding="utf-8"))["tasks"][0]
    with open(args.data_dir / args.dataset / "records.jsonl", encoding="utf-8") as f:
        test = [r for r in map(json.loads, f) if r["label_mode"] == "blind"]
    if args.limit:
        test = test[: args.limit]

    engine = DecisionEngine(model_name_or_path=MODEL)
    query = Choice(id="label", question=task["question"],
                   options=[Option(id=k, description=v) for k, v in task["labels"].items()])
    lines, abstained = [], 0
    for r in test:
        t0 = time.perf_counter()
        res = engine.evaluate(r["text"], [query]).results[0]
        latency_ms = (time.perf_counter() - t0) * 1000
        abstained += res.is_abstention
        label = max(task["labels"], key=lambda k: res.probabilities[k])
        lines.append({"external_id": r["external_id"], "budget": 0, "seed": 0, "label": label,
                      "latency_ms": round(latency_ms, 4), "abstained": res.is_abstention,
                      "confidence": round(res.probabilities[label], 4)})

    out = args.out / args.dataset
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{SYSTEM}.jsonl", "w", encoding="utf-8") as f:
        for ln in lines:
            f.write(json.dumps(ln) + "\n")
    meta = {"kind": "local", "model": MODEL, "abstention_ranked_first": abstained, "n": len(lines)}
    (out / f"{SYSTEM}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    f1 = f1_score([r["label"] for r in test], [ln["label"] for ln in lines], average="macro", zero_division=0)
    print(f"{args.dataset}  {SYSTEM} zero-shot: macro-F1 {f1:.3f} on {len(lines)} records "
          f"(abstention ranked first on {abstained})")


if __name__ == "__main__":
    main(sys.argv[1:])
