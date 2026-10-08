"""T2.7 acceptance tests: the built image serves and trains with ``LayaBackend``.

Starts its own containers; skipped unless ``IMAGE`` is set::

    IMAGE=decider-ai:dev SEED_HF_CACHE=~/.cache/huggingface/hub \\
    RELEASE_FIXTURE=data/release-fixture/records.jsonl \\
    uv run pytest -m laya tests/container -v

- ``SEED_HF_CACHE``: optional host HF hub dir holding the base checkpoint; copied into
  the test volume so nothing is downloaded. Unset, the first start downloads it.
- ``DOCKER_LIMITS``: extra ``docker run`` flags (default ``--cpus 3 --memory 10g``).
- ``PORT`` (default 18087). The test never prints message texts.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import pytest

IMAGE = os.environ.get("IMAGE")
pytestmark = [
    pytest.mark.laya,
    pytest.mark.skipif(not IMAGE, reason="set IMAGE to a built decider-ai image"),
]

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(os.environ.get("RELEASE_FIXTURE", ROOT / "data/release-fixture/records.jsonl"))
SEED = os.environ.get("SEED_HF_CACHE")
LIMITS = shlex.split(os.environ.get("DOCKER_LIMITS", "--cpus 3 --memory 10g"))
PORT = int(os.environ.get("PORT", "18087"))
KEY = "t27-key"
CKPT = "models--convaiinnovations--laya-multilingual"


def sh(*args: str, input: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, input=input, capture_output=True, text=True, check=check)


def in_vol(vol: str, cmd: str, input: str | None = None) -> str:
    return sh("docker", "run", "--rm", "-i", "-v", f"{vol}:/data", "--entrypoint", "sh",
              IMAGE, "-c", cmd, input=input).stdout


def records() -> list[dict]:
    with FIXTURE.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def release_tasks(limit: int) -> str:
    """tests/release/tasks.yaml with ``max_input_tokens`` of ``massive_zs`` set to ``limit``."""
    text = (ROOT / "tests/release/tasks.yaml").read_text(encoding="utf-8")
    first, rest = text.split("max_input_tokens: 512", 1)
    return f"{first}max_input_tokens: {limit}{rest}"


@pytest.fixture(scope="module")
def volume():
    vol = f"t27-{uuid.uuid4().hex[:8]}"
    sh("docker", "volume", "create", vol)
    if SEED:
        sh("docker", "run", "--rm", "-v", f"{os.path.expanduser(SEED)}:/host:ro", "-v", f"{vol}:/data",
           "--entrypoint", "sh", IMAGE, "-c", f"mkdir -p /data/hf-cache && cp -rL /host/{CKPT} /data/hf-cache/")
    yield vol
    sh("docker", "volume", "rm", "-f", vol, check=False)


def start(vol: str, name: str, timeout: float = 900) -> httpx.Client:
    sh("docker", "run", "-d", "--name", name, *LIMITS, "-p", f"127.0.0.1:{PORT}:8080",
       "-e", f"DECIDER_API_KEY={KEY}", "-v", f"{vol}:/data", IMAGE)
    c = httpx.Client(base_url=f"http://127.0.0.1:{PORT}",
                     headers={"Authorization": f"Bearer {KEY}"}, timeout=120)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if c.get("/health/live").status_code == 200:
                return c
        except httpx.TransportError:
            pass
        running = sh("docker", "inspect", "-f", "{{.State.Running}}", name).stdout.strip()
        assert running == "true", sh("docker", "logs", name, check=False).stderr[-2000:]
        time.sleep(2)
    raise AssertionError(f"{name} not live after {timeout}s")


def test_over_budget_task_refuses_to_start(volume):
    vol = f"{volume}-bad"
    sh("docker", "volume", "create", vol)
    try:
        sh("docker", "run", "--rm", "-v", f"{volume}:/seed:ro", "-v", f"{vol}:/data",
           "--entrypoint", "sh", IMAGE, "-c", "[ ! -d /seed/hf-cache ] || cp -a /seed/hf-cache /data/")
        long = "Very long description of this label that goes on " * 6
        labels = "".join(f"      l{i}: {long}\n" for i in range(12))
        yaml = f"tasks:\n  - name: big\n    question: Which one?\n    zero_shot: true\n    labels:\n{labels}"
        in_vol(vol, "cat > /data/tasks.yaml", input=yaml)
        out = sh("docker", "run", "--rm", *LIMITS, "-e", f"DECIDER_API_KEY={KEY}", "-v", f"{vol}:/data",
                 IMAGE, check=False)
        assert out.returncode != 0
        assert "decider-ai cannot start: task 'big': question and label descriptions need" in out.stderr
    finally:
        sh("docker", "volume", "rm", "-f", vol, check=False)


def test_laya_in_container(volume):
    recs = records()
    # A MASSIVE text whose exact token count becomes massive_zs's limit.
    at_limit = " ".join(r["text"] for r in recs[:3])
    count = ("import sys; from decider.backend.laya import LayaBackend; "
             "print(LayaBackend(cache_dir='/data/hf-cache').count_tokens(sys.stdin.read()))")
    if SEED:
        limit = int(sh("docker", "run", "--rm", "-i", "--network", "none", "-v", f"{volume}:/data",
                       "--entrypoint", "python", IMAGE, "-c", count, input=at_limit).stdout.split()[-1])
    else:
        limit = None  # set after the first start downloaded the checkpoint
    in_vol(volume, "cat > /data/tasks.yaml", input=release_tasks(limit or 512))

    name = f"{volume}-c"
    try:
        c = start(volume, name)
        if limit is None:
            sh("docker", "rm", "-f", name)
            limit = int(sh("docker", "run", "--rm", "-i", "-v", f"{volume}:/data", "--entrypoint",
                           "python", IMAGE, "-c", count, input=at_limit).stdout.split()[-1])
            in_vol(volume, "cat > /data/tasks.yaml", input=release_tasks(limit))
            c = start(volume, name)

        # Zero-shot: the real base model, a score per label.
        r = c.post("/v1/decisions", json={"task": "massive_zs", "text": recs[0]["text"]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["model_version"] == "base"
        labels = {"alarm", "audio", "calendar", "cooking", "datetime", "email", "general", "iot",
                  "lists", "music", "news", "play", "qa", "recommendation", "social", "takeaway",
                  "transport", "weather"}
        assert set(d["predictions"]) == labels

        # Exactly at the limit is served; one more word is 413 INPUT_TOO_LONG.
        r = c.post("/v1/decisions", json={"task": "massive_zs", "text": at_limit})
        assert r.status_code == 200, r.text
        r = c.post("/v1/decisions", json={"task": "massive_zs", "text": at_limit + " " + recs[3]["text"]})
        assert r.status_code == 413 and r.json()["error"]["code"] == "INPUT_TOO_LONG", r.text

        # Import 60 fixture examples, retrain, watch the job, decide during training.
        body = "".join(json.dumps({**x, "task": "massive"}, ensure_ascii=False) + "\n" for x in recs[:60])
        r = c.post("/v1/examples:batch", content=body.encode(),
                   headers={"Content-Type": "application/x-ndjson"})
        assert r.status_code == 200
        assert all(o["outcome"] != "rejected" for o in r.json()["outcomes"]), r.json()
        r = c.post("/v1/retrain", json={"task": "massive"})
        assert r.status_code == 202, r.text
        job_id = r.json()["job_id"]
        seen, during = set(), []
        deadline = time.monotonic() + float(os.environ.get("JOB_TIMEOUT", 5400))
        while True:
            job = c.get(f"/v1/jobs/{job_id}").json()
            if job["state"] != "running":
                break
            seen.add(job["progress"])
            if len(during) < 3 and 0 < job["progress"] < 1:
                r = c.post("/v1/decisions", json={"task": "massive_zs", "text": recs[1]["text"]})
                during.append(r.status_code)
            assert time.monotonic() < deadline, "retrain job did not finish"
            time.sleep(5)
        assert job["state"] == "succeeded", job["error"]
        assert any(0 < p < 1 for p in seen), f"no intermediate progress seen: {sorted(seen)}"
        assert during and all(s == 200 for s in during), during
        assert job["verdict"] == "unverified"
        found = sh("docker", "exec", name, "find", f"/data/models/massive/{job_id}",
                   "-name", "*.safetensors").stdout
        assert found.strip(), "no candidate checkpoint under /data/models"
        assert job["version"] in [m["version"] for m in c.get("/v1/tasks/massive/models").json()["models"]]
    finally:
        sh("docker", "rm", "-f", name, check=False)
