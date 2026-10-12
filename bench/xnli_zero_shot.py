"""Zero-shot predictions from XLM-R Large fine-tuned on XNLI: each label description is an NLI hypothesis.

    uv run --group bench python bench/xnli_zero_shot.py --dataset massive_en_scenario
    uv run --group bench python bench/xnli_zero_shot.py --dataset massive_de_scenario \\
        --template "Dabei geht es um: {}."

Reads <data-dir>/<dataset>/records.jsonl (test = label_mode blind) and <tasks-dir>/<dataset>.yaml
(label descriptions), scores "text entails <template with description>" for every label in one batch
per text, and writes
    <out>/<dataset>/xlmr_large_xnli.jsonl      one line per test record, budget 0 seed 0 (zero-shot)
    <out>/<dataset>/xlmr_large_xnli.meta.json  kind "local"
The label is the one with the highest entailment-vs-contradiction probability ("confidence").
Prints aggregate macro-F1 only.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import torch
import yaml
from sklearn.metrics import f1_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL = "joeddav/xlm-roberta-large-xnli"
SYSTEM = "xlmr_large_xnli"


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--tasks-dir", type=Path, default=Path("bench/tasks"))
    p.add_argument("--out", type=Path, default=Path("predictions"))
    p.add_argument("--dataset", default="massive_en_scenario")
    p.add_argument("--template", default="This is about: {}.", help="hypothesis; {} = label description")
    p.add_argument("--limit", type=int, default=0, help="smoke test: cap test records")
    args = p.parse_args(argv)

    task = yaml.safe_load((args.tasks_dir / f"{args.dataset}.yaml").read_text(encoding="utf-8"))["tasks"][0]
    with open(args.data_dir / args.dataset / "records.jsonl", encoding="utf-8") as f:
        test = [r for r in map(json.loads, f) if r["label_mode"] == "blind"]
    if args.limit:
        test = test[: args.limit]

    # The XNLI repo ships only the sentencepiece file; XLM-R Large has the same vocabulary as tokenizer.json.
    tok = AutoTokenizer.from_pretrained("FacebookAI/xlm-roberta-large")
    model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval()
    ids = {v.lower(): k for k, v in model.config.id2label.items()}
    pair = [ids["contradiction"], ids["entailment"]]
    labels = list(task["labels"])
    hypotheses = [args.template.format(task["labels"][k]) for k in labels]

    lines = []
    with torch.inference_mode():
        for r in test:
            t0 = time.perf_counter()
            enc = tok([r["text"]] * len(labels), hypotheses, padding=True, truncation=True, max_length=128,
                      return_tensors="pt")
            entail = model(**enc).logits[:, pair].softmax(-1)[:, 1]
            best = int(entail.argmax())
            lines.append({"external_id": r["external_id"], "budget": 0, "seed": 0, "label": labels[best],
                          "latency_ms": round((time.perf_counter() - t0) * 1000, 4),
                          "confidence": round(float(entail[best]), 4)})

    out = args.out / args.dataset
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{SYSTEM}.jsonl", "w", encoding="utf-8") as f:
        for ln in lines:
            f.write(json.dumps(ln) + "\n")
    meta = {"kind": "local", "model": MODEL, "template": args.template, "n": len(lines)}
    (out / f"{SYSTEM}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    f1 = f1_score([r["label"] for r in test], [ln["label"] for ln in lines], average="macro", zero_division=0)
    print(f"{args.dataset}  {SYSTEM} zero-shot: macro-F1 {f1:.3f} on {len(lines)} records")


if __name__ == "__main__":
    main(sys.argv[1:])
