"""Convert the downloaded sets into decider-ai records and training subsets.

    python bench/convert.py [--data-dir data] [--budgets 50,100,250] [--seeds 0-4]

Writes, per dataset (massive_de_scenario, clinc_domain):
    data/<dataset>/records.jsonl          official train (assisted) + test (blind)
    data/<dataset>/subsets/<budget>-<seed>.json   list of train external_ids
Prints counts only, never message text.
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path


def record(external_id: str, text: str, label: str, partition: str) -> dict:
    return {
        "external_id": external_id,
        "text": text,
        "label": label,
        "group_id": external_id,
        "label_mode": "blind" if partition == "test" else "assisted",
    }


def convert_massive(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["partition"] in ("train", "test"):
                out.append(record(f"massive-de-DE-{row['id']}", row["utt"], row["scenario"], row["partition"]))
    return out


def convert_clinc(data_path: Path, domains_path: Path) -> list[dict]:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    domain_of = {intent: d for d, intents in json.loads(domains_path.read_text(encoding="utf-8")).items() for intent in intents}
    out = []
    for split in ("train", "test"):
        rows = data[split] + data["oos_" + split]  # in-scope first, then out-of-scope
        for i, (text, intent) in enumerate(rows):
            label = "out_of_scope" if intent == "oos" else domain_of[intent]
            out.append(record(f"clinc-{split}-{i}", text, label, split))
    return out


def subset(train: list[dict], budget, seed: int) -> list[str]:
    """One example per label first (sorted labels), then random fill; seeded. budget "all" = whole train."""
    if budget == "all":
        return [r["external_id"] for r in train]
    rng = random.Random(seed)
    labels = sorted({r["label"] for r in train})
    if budget < len(labels):
        raise ValueError(f"budget {budget} is smaller than the {len(labels)} labels")
    picked = [rng.choice([r["external_id"] for r in train if r["label"] == lab]) for lab in labels]
    taken = set(picked)
    rest = [r["external_id"] for r in train if r["external_id"] not in taken]
    return picked + rng.sample(rest, budget - len(picked))


def write_dataset(records: list[dict], out_dir: Path, budgets, seeds) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "records.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    train = [r for r in records if r["label_mode"] == "assisted"]
    (out_dir / "subsets").mkdir(exist_ok=True)
    for b in budgets:
        for s in seeds:
            (out_dir / "subsets" / f"{b}-{s}.json").write_text(json.dumps(subset(train, b, s)))


def summary(name: str, records: list[dict]) -> str:
    lines = [name]
    for mode, part in (("assisted", "train"), ("blind", "test")):
        c = Counter(r["label"] for r in records if r["label_mode"] == mode)
        lines.append(f"  {part} ({mode}): {sum(c.values())}  " + " ".join(f"{k}={v}" for k, v in sorted(c.items())))
    return "\n".join(lines)


def parse_seeds(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--budgets", default="50,100,250", help='comma list; "all" = whole train partition')
    p.add_argument("--seeds", default="0-4")
    args = p.parse_args(argv)
    budgets = [b if b == "all" else int(b) for b in args.budgets.split(",")]
    seeds = parse_seeds(args.seeds)
    raw = args.data_dir / "raw"
    datasets = {
        "massive_de_scenario": convert_massive(raw / "massive_de-DE.jsonl"),
        "clinc_domain": convert_clinc(raw / "clinc_data_oos_plus.json", raw / "clinc_domains.json"),
    }
    for name, records in datasets.items():
        write_dataset(records, args.data_dir / name, budgets, seeds)
        print(summary(name, records))
        print(f"  subsets: budgets {budgets} x seeds {seeds} -> {args.data_dir / name / 'subsets'}")


if __name__ == "__main__":
    main(sys.argv[1:])
