"""Download the pinned public benchmark files and verify their sha256.

    python bench/fetch.py                    # download into data/raw (idempotent)
    python bench/fetch.py --release-fixture  # also write data/release-fixture/

Pins: docs/research/public-benchmark-datasets.md. Datasets are downloaded,
never committed (docs/adr/0001-licensing.md).
"""

import argparse
import hashlib
import json
import random
import shutil
import sys
import tarfile
import urllib.request
from collections import defaultdict
from pathlib import Path

MASSIVE_URL = "https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz"
CLINC_BASE = "https://raw.githubusercontent.com/clinc/oos-eval/828f8093932c8fe6ca7936c3d2e52903b1c523de/data/"

# local name -> (url, sha256)
FILES = {
    "amazon-massive-dataset-1.1.tar.gz": (
        MASSIVE_URL,
        "4cba5faa11c71437928e17cb1b9b3d8b8e727e7ea363a3a9a8045e19c0491577",
    ),
    "clinc_data_oos_plus.json": (
        CLINC_BASE + "data_oos_plus.json",
        "bfcca9ae515623541dc1983c94c4ed7cae9d26b42ae47d74b972e51bb6f7a21f",
    ),
    # Not in the research doc; hashed at the same pinned commit on 2026-10-08.
    "clinc_domains.json": (
        CLINC_BASE + "domains.json",
        "b947b579d3b8e74b06f93b01083d8efaff2888b43a3e362533bd88a6e1211b3a",
    ),
}

# Members extracted from the MASSIVE tarball: member -> (local name, sha256 or None)
MASSIVE_MEMBERS = {
    "1.1/data/de-DE.jsonl": (
        "massive_de-DE.jsonl",
        "5e09cc550b38d37faf002e0ff42103acd330906e23032689e8f071e1cf3ff621",
    ),
    "1.1/LICENSE": ("massive_LICENSE", None),
}

NOTICE = (
    "This fixture contains 200 utterances from MASSIVE 1.1 (locale de-DE, train partition),\n"
    "Copyright Amazon.com, Inc., licensed under CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/); MASSIVE is derived from SLURP (CC BY 4.0).\n"
    "Source: https://github.com/alexa/massive "
    "(commit f966f21846043aabef9b0f974fa7970027f43738), " + MASSIVE_URL + "\n"
    "Changes: selected a subset, kept the scenario label, converted to decider-ai JSONL records.\n"
)


class HashMismatch(SystemExit):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise HashMismatch(f"sha256 mismatch for {path}: expected {expected}, actual {actual}")


def fetch_file(url: str, expected: str, dest: Path) -> bool:
    """Download url to dest unless present. Returns True if it downloaded."""
    if dest.exists():
        check(dest, expected)  # a tampered file fails; it is never silently replaced
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url) as r, open(part, "wb") as f:
        shutil.copyfileobj(r, f)
    try:
        check(part, expected)
    except HashMismatch:
        part.unlink()
        raise
    part.rename(dest)
    return True


def extract_massive(tarball: Path, raw: Path) -> None:
    with tarfile.open(tarball) as tf:
        for member, (name, expected) in MASSIVE_MEMBERS.items():
            dest = raw / name
            if not dest.exists():
                with tf.extractfile(member) as src, open(dest, "wb") as f:
                    shutil.copyfileobj(src, f)
            if expected:
                check(dest, expected)


def fetch_all(data_dir: Path, files=None) -> list[str]:
    raw = data_dir / "raw"
    downloaded = [name for name, (url, sha) in (files or FILES).items() if fetch_file(url, sha, raw / name)]
    tarball = raw / "amazon-massive-dataset-1.1.tar.gz"
    if tarball.exists():
        extract_massive(tarball, raw)
    return downloaded


def release_fixture(massive_jsonl: Path, out_dir: Path, *, size=200, per_label=10, seed=0) -> list[dict]:
    """Seeded, stratified MASSIVE de-DE train subset: per_label per scenario first, rest random."""
    by_label = defaultdict(list)
    with open(massive_jsonl, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["partition"] == "train":
                by_label[row["scenario"]].append(row)
    rng = random.Random(seed)
    chosen = []
    for label in sorted(by_label):
        chosen += rng.sample(by_label[label], per_label)
    taken = {r["id"] for r in chosen}
    rest = [r for label in sorted(by_label) for r in by_label[label] if r["id"] not in taken]
    chosen += rng.sample(rest, size - len(chosen))
    rng.shuffle(chosen)
    records = [
        {
            "external_id": f"massive-de-DE-{r['id']}",
            "text": r["utt"],
            "label": r["scenario"],
            "group_id": f"massive-de-DE-{r['id']}",
            "label_mode": "assisted",
        }
        for r in chosen
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "records.jsonl", "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (out_dir / "NOTICE").write_text(NOTICE, encoding="utf-8")
    licence = massive_jsonl.parent / "massive_LICENSE"
    if licence.exists():
        shutil.copy(licence, out_dir / "LICENSE")
    write_fixture_tasks(out_dir / "tasks.yaml")
    return records


def write_fixture_tasks(path: Path) -> None:
    """Two tasks with the MASSIVE scenario labels: massive_zs (zero-shot) and massive."""
    import yaml

    src = Path(__file__).parent / "tasks" / "massive_de_scenario.yaml"
    task = yaml.safe_load(src.read_text(encoding="utf-8"))["tasks"][0]
    tasks = [{**task, "name": "massive_zs", "zero_shot": True}, {**task, "name": "massive", "zero_shot": False}]
    path.write_text(yaml.safe_dump({"tasks": tasks}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--release-fixture", action="store_true")
    args = p.parse_args(argv)
    downloaded = fetch_all(args.data_dir)
    print(f"downloaded {len(downloaded)} file(s): {', '.join(downloaded) or 'none (all present, sha256 ok)'}")
    if args.release_fixture:
        out = args.data_dir / "release-fixture"
        records = release_fixture(args.data_dir / "raw" / "massive_de-DE.jsonl", out)
        print(f"release fixture: {len(records)} records -> {out}/records.jsonl (+ NOTICE, LICENSE, tasks.yaml)")


if __name__ == "__main__":
    main(sys.argv[1:])
