"""Score the serving model on a labelled sheet and show good and bad examples.

Runs inside the decider-ai container, where openpyxl is installed and the API key sits in /data:

    docker cp sheet.xlsx decider-ai:/tmp/sheet.xlsx
    docker exec -i decider-ai python - /tmp/sheet.xlsx --task route \
        --text-column Message --label-column Team < check.py

Prints one JSON object: accuracy, macro-F1, per-label recall and a few right and wrong decisions.
"""

import argparse
import csv
import io
import json
import os
import random
import urllib.request
from collections import Counter
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl

        sheet = openpyxl.load_workbook(path, read_only=True, data_only=True).active
        grid = [["" if v is None else str(v) for v in r] for r in sheet.iter_rows(values_only=True)]
    else:
        text = path.read_text(encoding="utf-8-sig")
        try:
            dialect = csv.Sniffer().sniff(text.split("\n", 1)[0], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        grid = list(csv.reader(io.StringIO(text), dialect))
    grid = [r for r in grid if any(c.strip() for c in r)]
    header = [h.strip() for h in grid[0]]
    return [dict(zip(header, (c.strip() for c in r))) for r in grid[1:]]


def decide(url: str, key: str, task: str, text: str) -> dict:
    req = urllib.request.Request(
        f"{url}/v1/decisions", json.dumps({"task": task, "text": text}).encode(),
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("sheet", type=Path)
    p.add_argument("--task", required=True)
    p.add_argument("--text-column", default="text")
    p.add_argument("--label-column", default="label")
    p.add_argument("--sample", type=int, default=200)
    p.add_argument("--show", type=int, default=5)
    p.add_argument("--url", default="http://127.0.0.1:8080")
    a = p.parse_args()
    key = os.environ.get("DECIDER_API_KEY") or Path("/data/api_key").read_text().strip()

    data = [(r[a.text_column], r[a.label_column]) for r in rows(a.sheet)
            if r.get(a.text_column) and r.get(a.label_column)]
    random.Random(0).shuffle(data)
    data = data[:a.sample]
    right, wrong, model, skipped = [], [], None, Counter()
    for text, gold in data:
        d = decide(a.url, key, a.task, text)
        model = d["model_version"]
        if gold not in d["predictions"]:  # not a label of the task; the import rejects it too
            skipped[gold] += 1
            continue
        top = max(d["predictions"], key=d["predictions"].get)
        (right if top == gold else wrong).append({"text": text[:200], "label": gold, "model": top})

    n = len(right) + len(wrong)
    labels = sorted({x["label"] for x in right + wrong})
    tp = Counter(x["label"] for x in right)
    fn = Counter(x["label"] for x in wrong)
    fp = Counter(x["model"] for x in wrong)
    f1 = [2 * tp[l] / (2 * tp[l] + fn[l] + fp[l]) if tp[l] + fn[l] + fp[l] else 0.0 for l in labels]
    print(json.dumps({
        "model_version": model,
        "n": n,
        "skipped_unknown_labels": dict(skipped),
        "accuracy": round(len(right) / n, 3) if n else None,
        "macro_f1": round(sum(f1) / len(f1), 3) if f1 else None,
        "recall": {l: f"{tp[l]}/{tp[l] + fn[l]}" for l in labels},
        "confusions": Counter(f"{x['label']} -> {x['model']}" for x in wrong).most_common(5),
        "good": right[:a.show],
        "bad": wrong[:a.show],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
