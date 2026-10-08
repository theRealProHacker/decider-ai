"""Run the majority and TF-IDF + logistic regression baselines.

    python bench/baselines.py [--data-dir data] [--out predictions] [--datasets massive_de_scenario,clinc_domain]

Reads data/<dataset>/records.jsonl and every data/<dataset>/subsets/<budget>-<seed>.json
(written by bench/convert.py) and writes, per dataset and system:
    predictions/<dataset>/<system>.jsonl      one line per test record and (budget, seed)
    predictions/<dataset>/<system>.meta.json  kind "local", training seconds per (budget, seed)
latency_ms is measured per prediction, one text at a time. Prints aggregate macro-F1 only.
scikit-learn lives in the bench dependency group; src/decider never imports this.
"""

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import make_pipeline, make_union


class Majority:
    def fit(self, texts, labels):
        counts = Counter(labels)
        # most frequent label, ties broken by sorted label name
        self.label = min(counts, key=lambda lab: (-counts[lab], lab))
        return self

    def predict(self, texts):
        return [self.label for _ in texts]


def tfidf_lr():
    # Spec: docs/research/public-benchmark-datasets.md, Baselines item 2.
    return make_pipeline(
        make_union(
            TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True),
            TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True),
        ),
        LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000),
    )


SYSTEMS = {"majority": Majority, "tfidf_lr": tfidf_lr}


def load_records(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_subsets(subset_dir: Path) -> dict[tuple, list[str]]:
    out = {}
    for p in sorted(subset_dir.glob("*.json")):
        budget, seed = p.stem.rsplit("-", 1)
        out[(int(budget) if budget.isdigit() else budget, int(seed))] = json.loads(p.read_text())
    return out


def run_system(make_model, records, subsets):
    """Returns (prediction lines, training seconds per "budget-seed")."""
    by_id = {r["external_id"]: r for r in records}
    test = [r for r in records if r["label_mode"] == "blind"]
    lines, train_seconds = [], {}
    for (budget, seed), ids in subsets.items():
        train = [by_id[i] for i in ids]
        t0 = time.perf_counter()
        model = make_model().fit([r["text"] for r in train], [r["label"] for r in train])
        train_seconds[f"{budget}-{seed}"] = round(time.perf_counter() - t0, 4)
        for r in test:
            t0 = time.perf_counter()
            label = model.predict([r["text"]])[0]
            latency_ms = (time.perf_counter() - t0) * 1000
            lines.append(
                {
                    "external_id": r["external_id"],
                    "budget": budget,
                    "seed": seed,
                    "label": str(label),
                    "latency_ms": round(latency_ms, 4),
                }
            )
    return lines, train_seconds


def macro_f1_by_budget(records, lines) -> dict:
    gold = {r["external_id"]: r["label"] for r in records}
    groups = defaultdict(lambda: ([], []))
    for ln in lines:
        g, p = groups[(ln["budget"], ln["seed"])]
        g.append(gold[ln["external_id"]])
        p.append(ln["label"])
    per_budget = defaultdict(list)
    for (budget, _seed), (g, p) in groups.items():
        per_budget[budget].append(f1_score(g, p, average="macro", zero_division=0))
    return {b: (statistics.mean(v), statistics.pstdev(v), len(v)) for b, v in per_budget.items()}


def run_dataset(data_dir: Path, out_dir: Path, systems=SYSTEMS) -> dict:
    records = load_records(data_dir / "records.jsonl")
    subsets = load_subsets(data_dir / "subsets")
    out_dir.mkdir(parents=True, exist_ok=True)
    scores = {}
    for name, make_model in systems.items():
        lines, train_seconds = run_system(make_model, records, subsets)
        with open(out_dir / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for ln in lines:
                f.write(json.dumps(ln) + "\n")
        meta = {"kind": "local", "train_seconds": train_seconds}
        (out_dir / f"{name}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        scores[name] = macro_f1_by_budget(records, lines)
    return scores


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--out", type=Path, default=Path("predictions"))
    p.add_argument("--datasets", default="massive_de_scenario,clinc_domain")
    args = p.parse_args(argv)
    for ds in args.datasets.split(","):
        scores = run_dataset(args.data_dir / ds, args.out / ds)
        for system, by_budget in scores.items():
            for budget, (mean, sd, n) in sorted(by_budget.items(), key=lambda kv: str(kv[0]).zfill(8)):
                print(f"{ds}  {system:9s} budget {budget}: macro-F1 {mean:.3f} (sd {sd:.3f}, {n} seeds)")


if __name__ == "__main__":
    main(sys.argv[1:])
