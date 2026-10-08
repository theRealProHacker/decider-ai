"""Phase 1 release test (build-plan T2.8, design.md Success Criteria), over HTTP.

Runs against a running decider-ai container; skipped unless ``DECIDER_API_KEY`` is set.

Steps:

1. Fetch the fixture (200 MASSIVE 1.1 de-DE scenario records)::

       uv run --group bench python bench/fetch.py --release-fixture
       # writes data/release-fixture/records.jsonl

2. Start the container with ``tests/release/tasks.yaml`` as its ``tasks.yaml``
   (tasks ``massive_zs``, zero-shot, and ``massive``, not zero-shot), a fresh data
   volume and an API key, e.g. ``--name decider-release -p 8080:8080``.

3. Run::

       DECIDER_URL=http://127.0.0.1:8080 DECIDER_API_KEY=... \\
       DECIDER_CONTAINER=decider-release \\
       uv run pytest -m release tests/release -v

Environment:

- ``DECIDER_URL`` (default ``http://127.0.0.1:8080``), ``DECIDER_API_KEY`` (required).
- ``RELEASE_FIXTURE`` (default ``data/release-fixture/records.jsonl``).
- ``DECIDER_CONTAINER``: the container name for ``docker restart``. Unset, the
  restart check of step 4 is skipped.
- ``RELEASE_JOB_TIMEOUT``: seconds to wait for one retrain job (default 3600).

The test needs a fresh data volume: it expects zero confirmed examples at the start.
It never prints message texts.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Callable

import httpx
import pytest

pytestmark = pytest.mark.release

ZS, NZ = "massive_zs", "massive"
STAGE_A = 60
FEEDBACK = {"task": NZ, "text": "stell bitte einen wecker für morgen um sieben",
            "label": "alarm", "external_id": "release-feedback-1"}


def load_records(path: str | Path, task: str = NZ) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [{**json.loads(line), "task": task} for line in f if line.strip()]


def ok(r: httpx.Response, status: int = 200) -> dict:
    # The body never echoes a message text, so it is safe in the failure message.
    assert r.status_code == status, f"{r.request.method} {r.request.url.path}: {r.status_code} {r.text}"
    return r.json()


def import_examples(c, rows: list[dict]) -> None:
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    out = ok(c.post("/v1/examples:batch", content=body.encode(),
                    headers={"Content-Type": "application/x-ndjson"}))["outcomes"]
    rejected = [o for o in out if o["outcome"] == "rejected"]
    assert len(out) == len(rows) and not rejected, rejected


def ready(c, task: str = NZ) -> dict:
    return ok(c.get("/health/ready"))["tasks"][task]


def decide_version(c, task: str, text: str) -> str:
    return ok(c.post("/v1/decisions", json={"task": task, "text": text}))["model_version"]


def retrain(c, task: str = NZ, timeout: float = 3600) -> dict:
    job_id = ok(c.post("/v1/retrain", json={"task": task}), 202)["job_id"]
    deadline = time.monotonic() + timeout
    while True:
        job = ok(c.get(f"/v1/jobs/{job_id}"))
        if job["state"] != "running":
            assert job["state"] == "succeeded", job.get("error")
            return job
        assert time.monotonic() < deadline, f"job {job_id} still running after {timeout}s"
        time.sleep(2)


def active_in_models(c, task: str = NZ) -> list[str]:
    return [m["version"] for m in ok(c.get(f"/v1/tasks/{task}/models"))["models"] if m["active"]]


def run_release(c, records: list[dict], restart: Callable[[], None] | None,
                job_timeout: float = 3600) -> None:
    """Steps 1-4 of the Phase 1 release test. ``c`` is an authenticated client."""
    probe = records[0]["text"]
    assert ready(c)["confirmed"] == 0, "the release test needs a fresh data volume"

    # 1. Cold start.
    assert decide_version(c, ZS, probe) == "base"
    r = c.post("/v1/decisions", json={"task": NZ, "text": probe})
    assert r.status_code == 503 and r.json()["error"]["code"] == "MODEL_NOT_TRAINED", r.text

    # 2. Below 150 examples: import stage A, one feedback, retrain, activate the unverified candidate.
    import_examples(c, records[:STAGE_A])
    assert ok(c.post("/v1/feedback", json=FEEDBACK))["outcome"] == "added"
    assert ready(c)["confirmed"] == STAGE_A + 1
    job = retrain(c, timeout=job_timeout)
    first = job["version"]
    assert job["verdict"] == "unverified", job["verdict"]
    act = ok(c.post(f"/v1/tasks/{NZ}/models/{first}/activate"))
    assert act["warning"], "activating an unverified model must warn"
    assert decide_version(c, NZ, probe) == first

    # 3. Split frozen: import stage B, retrain; the active model stays until activate.
    import_examples(c, records[STAGE_A:])
    assert ready(c)["confirmed"] == len(records) + 1 >= 150
    job = retrain(c, timeout=job_timeout)
    second = job["version"]
    assert second != first
    assert job["verdict"] in ("recommended", "not_recommended"), job["verdict"]
    assert {"delta", "ci_low", "ci_high"} <= job["metrics"].keys(), job["metrics"]
    assert ready(c)["split"]["state"] == "frozen"
    assert decide_version(c, NZ, probe) == first
    assert active_in_models(c) == [first]
    assert ready(c)["active_version"] == first
    ok(c.post(f"/v1/tasks/{NZ}/models/{second}/activate"))
    assert decide_version(c, NZ, probe) == second

    # 4. Roll back, delete one example, restart without losing labels or the active version.
    ok(c.post(f"/v1/tasks/{NZ}/models/{first}/activate"))
    assert decide_version(c, NZ, probe) == first
    before = ready(c)["confirmed"]
    ok(c.delete(f"/v1/examples/{FEEDBACK['external_id']}"))
    status = ready(c)
    assert status["confirmed"] == before - 1
    if restart is None:
        pytest.skip("DECIDER_CONTAINER unset: restart check skipped (steps 1-4 up to delete passed)")
    restart()
    after = ready(c)
    assert after["confirmed"] == status["confirmed"]
    assert after["active_version"] == first
    assert decide_version(c, NZ, probe) == first


def docker_restart(base_url: str, container: str) -> Callable[[], None]:
    def restart() -> None:
        subprocess.run(["docker", "restart", container], check=True, capture_output=True)
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{base_url}/health/live", timeout=5).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(2)
        raise AssertionError(f"{container} not live 600s after docker restart")

    return restart


def test_phase1_release():
    key = os.environ.get("DECIDER_API_KEY")
    if not key:
        pytest.skip("release test: set DECIDER_API_KEY (and DECIDER_URL) for a running container")
    url = os.environ.get("DECIDER_URL", "http://127.0.0.1:8080").rstrip("/")
    fixture = Path(os.environ.get("RELEASE_FIXTURE", "data/release-fixture/records.jsonl"))
    assert fixture.exists(), f"{fixture} missing: run bench/fetch.py --release-fixture"
    container = os.environ.get("DECIDER_CONTAINER")
    restart = docker_restart(url, container) if container else None
    timeout = float(os.environ.get("RELEASE_JOB_TIMEOUT", 3600))
    with httpx.Client(base_url=url, headers={"Authorization": f"Bearer {key}"},
                      timeout=120) as c:
        run_release(c, load_records(fixture), restart, job_timeout=timeout)
