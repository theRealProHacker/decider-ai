import hashlib
import json
from collections import Counter

import pytest
import yaml

import fetch


def _serve(tmp_path, name, content: bytes):
    src = tmp_path / "upstream" / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(content)
    return src.as_uri(), hashlib.sha256(content).hexdigest()


def test_downloads_verifies_and_second_run_downloads_nothing(tmp_path):
    url, sha = _serve(tmp_path, "a.json", b"[1, 2, 3]")
    files = {"a.json": (url, sha)}
    data = tmp_path / "data"
    assert fetch.fetch_all(data, files) == ["a.json"]
    assert (data / "raw" / "a.json").read_bytes() == b"[1, 2, 3]"
    assert fetch.fetch_all(data, files) == []


def test_wrong_upstream_hash_fails_and_leaves_nothing(tmp_path):
    url, _ = _serve(tmp_path, "a.json", b"x")
    with pytest.raises(SystemExit, match="expected 00+, actual [0-9a-f]{64}"):
        fetch.fetch_all(tmp_path / "data", {"a.json": (url, "0" * 64)})
    assert not list((tmp_path / "data" / "raw").iterdir())


def test_tampered_local_file_fails_with_expected_and_actual(tmp_path):
    url, sha = _serve(tmp_path, "a.json", b"good")
    data = tmp_path / "data"
    fetch.fetch_all(data, {"a.json": (url, sha)})
    (data / "raw" / "a.json").write_bytes(b"evil")
    actual = hashlib.sha256(b"evil").hexdigest()
    with pytest.raises(SystemExit, match=f"expected {sha}, actual {actual}"):
        fetch.fetch_all(data, {"a.json": (url, sha)})


def _massive(tmp_path, per_label=15, labels=18):
    path = tmp_path / "massive_de-DE.jsonl"
    with open(path, "w") as f:
        i = 0
        for k in range(labels):
            for _ in range(per_label):
                for part in ("train", "test"):
                    f.write(json.dumps({"id": str(i), "partition": part, "scenario": f"s{k:02d}", "utt": f"u {i}"}) + "\n")
                    i += 1
    return path


def test_release_fixture_is_stratified_seeded_and_attributed(tmp_path):
    src = _massive(tmp_path)
    recs = fetch.release_fixture(src, tmp_path / "a")
    again = fetch.release_fixture(src, tmp_path / "b")
    assert len(recs) == 200
    assert (tmp_path / "a" / "records.jsonl").read_bytes() == (tmp_path / "b" / "records.jsonl").read_bytes()
    assert recs == again
    counts = Counter(r["label"] for r in recs)
    assert len(counts) == 18 and min(counts.values()) >= 10
    assert all(r["label_mode"] == "assisted" and r["group_id"] == r["external_id"] for r in recs)
    assert all(int(r["external_id"].rsplit("-", 1)[1]) % 2 == 0 for r in recs)  # train rows only
    assert "MASSIVE" in (tmp_path / "a" / "NOTICE").read_text() and "CC BY 4.0" in (tmp_path / "a" / "NOTICE").read_text()
    tasks = yaml.safe_load((tmp_path / "a" / "tasks.yaml").read_text())["tasks"]
    assert [(t["name"], t["zero_shot"]) for t in tasks] == [("massive_zs", True), ("massive", False)]
    assert len(tasks[0]["labels"]) == 18
