"""Fine-tune XLM-R Base on one training subset: the like-for-like reference for the MASSIVE paper.

    python bench/xlmr_baseline.py --data-dir data/8020 --out predictions/8020 \\
        --dataset massive_de_scenario --budget 11514 --seed 0

Reads <data-dir>/<dataset>/records.jsonl (test = label_mode blind) and
<data-dir>/<dataset>/subsets/<budget>-<seed>.json, and writes in bench/baselines.py's format:
    <out>/<dataset>/xlmr_base.jsonl      one line per test record
    <out>/<dataset>/xlmr_base.meta.json  kind "local", training seconds
latency_ms is measured per prediction, one text at a time. Prints aggregate macro-F1 only.
Hyperparameters follow common XLM-R fine-tuning defaults (AdamW, lr 2e-5, linear warmup).
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

import torch
from sklearn.metrics import f1_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

MODEL = "FacebookAI/xlm-roberta-base"
SYSTEM = "xlmr_base"


def load_records(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("data/8020"))
    p.add_argument("--out", type=Path, default=Path("predictions/8020"))
    p.add_argument("--dataset", default="massive_de_scenario")
    p.add_argument("--budget", type=int, default=11514)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--max-len", type=int, default=64)
    p.add_argument("--limit", type=int, default=0, help="smoke test: cap train and test records")
    args = p.parse_args(argv)

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    ddir = args.data_dir / args.dataset
    records = load_records(ddir / "records.jsonl")
    by_id = {r["external_id"]: r for r in records}
    train = [by_id[i] for i in json.loads((ddir / "subsets" / f"{args.budget}-{args.seed}.json").read_text())]
    test = [r for r in records if r["label_mode"] == "blind"]
    if args.limit:
        train, test = train[: args.limit], test[: args.limit]
    labels = sorted({r["label"] for r in records})
    lid = {lab: i for i, lab in enumerate(labels)}

    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL, num_labels=len(labels))
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    steps = args.epochs * -(-len(train) // args.batch_size)
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)

    t0 = time.perf_counter()
    model.train()
    for epoch in range(args.epochs):
        order = random.sample(train, len(train))
        total = 0.0
        for b in range(0, len(order), args.batch_size):
            batch = order[b : b + args.batch_size]
            enc = tok([r["text"] for r in batch], padding=True, truncation=True, max_length=args.max_len,
                      return_tensors="pt")
            loss = model(**enc, labels=torch.tensor([lid[r["label"]] for r in batch])).loss
            loss.backward()
            opt.step()
            sched.step()
            opt.zero_grad()
            total += loss.item() * len(batch)
        print(f"epoch {epoch + 1}/{args.epochs}: loss {total / len(order):.4f} "
              f"({time.perf_counter() - t0:.0f}s elapsed)", flush=True)
    train_seconds = time.perf_counter() - t0

    model.eval()
    lines = []
    with torch.inference_mode():
        for r in test:
            t1 = time.perf_counter()
            enc = tok([r["text"]], truncation=True, max_length=args.max_len, return_tensors="pt")
            label = labels[int(model(**enc).logits.argmax(-1))]
            lines.append({"external_id": r["external_id"], "budget": args.budget, "seed": args.seed,
                          "label": label, "latency_ms": round((time.perf_counter() - t1) * 1000, 4)})

    out = args.out / args.dataset
    out.mkdir(parents=True, exist_ok=True)
    # Keep other (budget, seed) runs already in the file: one file holds all subsets, as in baselines.py.
    key = f"{args.budget}-{args.seed}"
    pred_path, meta_path = out / f"{SYSTEM}.jsonl", out / f"{SYSTEM}.meta.json"
    kept = [ln for ln in (load_records(pred_path) if pred_path.exists() else [])
            if (ln["budget"], ln["seed"]) != (args.budget, args.seed)]
    with open(pred_path, "w", encoding="utf-8") as f:
        for ln in kept + lines:
            f.write(json.dumps(ln) + "\n")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    settings = {k: getattr(args, k) for k in ("epochs", "batch_size", "lr", "max_len")}
    meta = {"kind": "local", "model": MODEL,
            "train_seconds": {**meta.get("train_seconds", {}), key: round(train_seconds, 4)},
            "settings": {**meta.get("settings_by_run", {}), key: settings}}
    meta["settings_by_run"] = meta.pop("settings")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    f1 = f1_score([r["label"] for r in test], [ln["label"] for ln in lines], average="macro", zero_division=0)
    print(f"{args.dataset}  {SYSTEM} budget {args.budget}: macro-F1 {f1:.3f}, trained in {train_seconds / 3600:.2f} h")


if __name__ == "__main__":
    main(sys.argv[1:])
