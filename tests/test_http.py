import json
import logging

import pytest
from fastapi.testclient import TestClient

from decider.backend import ModelRef
from decider.backend.fake import FakeBackend
from decider.core import Decider
from decider.http import create_app
from decider.runner import InlineRunner, ManualRunner
from decider.tasks import TaskSpec

KEY = "secret-key"
AUTH = {"Authorization": f"Bearer {KEY}"}
LABELS = {"billing": "Money", "support": "Help", "sales": "Buy"}
NZ = TaskSpec("nz", "Which team?", LABELS)
ZS = TaskSpec("zs", "Which team?", LABELS, zero_shot=True)


@pytest.fixture
def make(tmp_path):
    made = []

    def make(runner=None, backend=None, max_body_bytes=None):
        d = Decider(
            [NZ, ZS],
            backend=backend or FakeBackend(max_tokens=50),
            runner=runner or InlineRunner(),
            db_path=tmp_path / "decider.db",
            model_dir=tmp_path / "models",
        )
        made.append(d)
        c = TestClient(create_app(d, KEY, max_body_bytes=max_body_bytes))
        c.headers.update(AUTH)
        return c

    yield make
    for d in made:
        d.close()


@pytest.fixture
def client(make):
    return make()


def fb(task="nz", i=0, label=None, **kw):
    return {"task": task, "text": f"{task} message {i}", "label": label or list(LABELS)[i % 3],
            "external_id": f"{task}-{i}", **kw}


def ndjson(rows):
    return "\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows) + "\n"


def feed(c, task, n):
    r = c.post("/v1/examples:batch", content=ndjson([fb(task, i) for i in range(n)]),
               headers={"Content-Type": "application/x-ndjson"})
    assert r.status_code == 200
    assert all(o["outcome"] != "rejected" for o in r.json()["outcomes"])


def err(r, status, code):
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code
    assert "message" in r.json()["error"]
    return r.json()["error"]


# --- auth ---------------------------------------------------------------------

ROUTES = [
    ("get", "/health/ready"),
    ("get", "/openapi.json"),
    ("post", "/v1/decisions"),
    ("post", "/v1/feedback"),
    ("post", "/v1/examples:batch"),
    ("delete", "/v1/examples/x"),
    ("post", "/v1/retrain"),
    ("get", "/v1/jobs/x"),
    ("get", "/v1/tasks/nz/models"),
    ("post", "/v1/tasks/nz/models/v1/activate"),
]


def test_live_needs_no_key(client):
    assert client.get("/health/live", headers={"Authorization": ""}).status_code == 200


@pytest.mark.parametrize("method,path", ROUTES)
@pytest.mark.parametrize("header", [None, "Bearer wrong", "Basic c2VjcmV0LWtleQ==", KEY])
def test_routes_need_the_key(client, method, path, header):
    client.headers.pop("Authorization")
    headers = {"Authorization": header} if header else {}
    r = client.request(method, path, headers=headers)
    err(r, 401, "UNAUTHORIZED")
    assert r.headers["WWW-Authenticate"] == "Bearer"


# --- decisions ------------------------------------------------------------------


def test_decision_zero_shot(client):
    r = client.post("/v1/decisions", json={"task": "zs", "text": "refund please"})
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == "base"
    assert body["request_id"]
    assert set(body["predictions"]) == set(LABELS)


def test_decision_errors(client):
    err(client.post("/v1/decisions", json={"task": "nz", "text": "hi"}), 503, "MODEL_NOT_TRAINED")
    e = err(client.post("/v1/decisions", json={"task": "nope", "text": "hi"}), 404,
            "TASK_NOT_FOUND")
    assert e["task"] == "nope"
    e = err(client.post("/v1/decisions", json={"task": "zs", "text": "word " * 51}), 413,
            "INPUT_TOO_LONG")
    assert e["limit"] == 50
    err(client.post("/v1/decisions", json={"task": "zs"}), 422, "VALIDATION_FAILED")
    err(client.post("/v1/decisions", content=b"not json",
                    headers={"Content-Type": "application/json"}), 422, "VALIDATION_FAILED")


# --- feedback and import ----------------------------------------------------------


def test_feedback_is_idempotent_on_external_id(client):
    r1 = client.post("/v1/feedback", json=fb())
    r2 = client.post("/v1/feedback", json=fb())
    assert (r1.status_code, r1.json()) == (200, {"outcome": "added"})
    assert (r2.status_code, r2.json()) == (200, {"outcome": "updated"})
    ready = client.get("/health/ready").json()
    assert ready["tasks"]["nz"]["confirmed"] == 1


def test_feedback_errors(client):
    e = err(client.post("/v1/feedback", json=fb(label="other")), 422, "LABEL_NOT_IN_TASK")
    assert e["allowed"] == list(LABELS)
    body = fb()
    del body["external_id"]
    err(client.post("/v1/feedback", json=body), 422, "VALIDATION_FAILED")
    err(client.post("/v1/feedback", json=fb(task="nope")), 404, "TASK_NOT_FOUND")
    err(client.post("/v1/feedback", json={**fb(), "text": "word " * 51}), 413, "INPUT_TOO_LONG")


def test_batch_outcomes_in_order(client):
    rows = [fb(i=0), fb(i=1, label="other"), "{not json", {"task": "nz"}, fb(i=0), fb(i=2)]
    r = client.post("/v1/examples:batch", content=ndjson(rows),
                    headers={"Content-Type": "application/x-ndjson"})
    assert r.status_code == 200
    assert r.json() == {"outcomes": [
        {"index": 0, "outcome": "added"},
        {"index": 1, "outcome": "rejected", "code": "LABEL_NOT_IN_TASK"},
        {"index": 2, "outcome": "rejected", "code": "VALIDATION_FAILED"},
        {"index": 3, "outcome": "rejected", "code": "VALIDATION_FAILED"},
        {"index": 4, "outcome": "updated"},
        {"index": 5, "outcome": "added"},
    ]}
    assert client.get("/health/ready").json()["tasks"]["nz"]["confirmed"] == 2


def test_batch_needs_ndjson(client):
    err(client.post("/v1/examples:batch", json=fb()), 422, "VALIDATION_FAILED")


# --- body cap ---------------------------------------------------------------------


def test_body_cap(make):
    c = make(max_body_bytes=200)
    small = fb()
    assert c.post("/v1/feedback", json=small).status_code == 200
    big = {**fb(), "text": "x" * 300}
    err(c.post("/v1/feedback", json=big), 413, "PAYLOAD_TOO_LARGE")

    def stream():  # chunked: no Content-Length
        yield json.dumps(big)[:150].encode()
        yield json.dumps(big)[150:].encode()

    r = c.post("/v1/feedback", content=stream(), headers={"Content-Type": "application/json"})
    assert "content-length" not in {k.lower() for k in r.request.headers}
    err(r, 413, "PAYLOAD_TOO_LARGE")
    r = c.post("/v1/examples:batch", content=stream(),
               headers={"Content-Type": "application/x-ndjson"})
    err(r, 413, "PAYLOAD_TOO_LARGE")


def test_body_cap_from_env(make, monkeypatch):
    monkeypatch.setenv("DECIDER_MAX_BODY_BYTES", "100")
    c = make()
    err(c.post("/v1/feedback", json={**fb(), "text": "x" * 200}), 413, "PAYLOAD_TOO_LARGE")


# --- forget -------------------------------------------------------------------------


def test_forget(client):
    client.post("/v1/feedback", json=fb())
    r = client.delete("/v1/examples/nz-0")
    assert r.status_code == 200
    assert r.json() == {"examples_removed": 1, "split_members_removed": 0,
                        "versions_trained_on": []}
    err(client.delete("/v1/examples/nz-0"), 404, "NOT_FOUND")


# --- retrain, jobs, models, activate -------------------------------------------------


def test_retrain_job_models_activate(client):
    feed(client, "nz", 60)
    r = client.post("/v1/retrain", json={"task": "nz"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    job = client.get(f"/v1/jobs/{job_id}").json()
    assert job["state"] == "succeeded" and job["progress"] == 1
    assert job["epoch"] is None and job["epochs"] is None  # FakeBackend reports no epochs
    assert job["verdict"] == "unverified"
    assert "metrics" in job
    err(client.get("/v1/jobs/nope"), 404, "NOT_FOUND")

    assert client.post("/v1/retrain", json={"task": "nz", "refresh_split": True}).status_code == 202

    models = client.get("/v1/tasks/nz/models").json()["models"]
    assert len(models) == 2
    for key in ("version", "verdict", "metrics", "split_revision", "split_size", "erased",
                "active"):
        assert key in models[0]
    err(client.get("/v1/tasks/nope/models"), 404, "TASK_NOT_FOUND")

    version = job["version"]
    r = client.post(f"/v1/tasks/nz/models/{version}/activate")
    assert r.status_code == 200
    assert "unverified" in r.json()["warning"]
    assert client.get("/v1/tasks/nz/models").json()["models"][0]["active"] is True
    d = client.post("/v1/decisions", json={"task": "nz", "text": "nz message 1"}).json()
    assert d["model_version"] == version
    err(client.post(f"/v1/tasks/zs/models/{version}/activate"), 404, "NOT_FOUND")


def test_retrain_errors(make):
    c = make(runner=ManualRunner())
    feed(c, "nz", 10)
    e = err(c.post("/v1/retrain", json={"task": "nz"}), 422, "TOO_FEW_EXAMPLES")
    assert (e["have"], e["need"]) == (10, 50)
    feed(c, "nz", 60)
    job_id = c.post("/v1/retrain", json={"task": "nz"}).json()["job_id"]
    assert c.get(f"/v1/jobs/{job_id}").json()["state"] == "running"
    e = err(c.post("/v1/retrain", json={"task": "nz"}), 409, "BUSY")
    assert e["job_id"] == job_id
    err(c.post("/v1/retrain", json={"task": "nope"}), 404, "TASK_NOT_FOUND")


def test_activation_failure(make):
    backend = FakeBackend(max_tokens=50)
    c = make(backend=backend)
    feed(c, "nz", 60)
    version = c.get(f"/v1/jobs/{c.post('/v1/retrain', json={'task': 'nz'}).json()['job_id']}"
                    ).json()["version"]
    backend.fail_predict(ModelRef(version))
    err(c.post(f"/v1/tasks/nz/models/{version}/activate"), 500, "ACTIVATION_FAILED")


# --- health, openapi ---------------------------------------------------------------------


def test_ready(client):
    tasks = client.get("/health/ready").json()["tasks"]
    assert tasks["zs"]["serving"] == "base" and tasks["zs"]["unmeasured"] is True
    nz = tasks["nz"]
    assert nz["serving"] == "not_trained"
    assert nz["input_limit"] == 50
    assert nz["active_version"] is None
    assert nz["confirmed"] == 0
    assert nz["split"] == {"state": "pending", "blocking_labels": list(LABELS)}
    assert nz["below_minimum"] == []


def test_openapi_served_docs_off(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/v1/decisions" in r.json()["paths"]
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


# --- no text in logs ------------------------------------------------------------------------


def test_no_text_in_logs(client, caplog):
    caplog.set_level(logging.DEBUG)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "decider"):
        logging.getLogger(name).setLevel(logging.DEBUG)
    sentinel = "SENTINEL-7f3a"
    client.post("/v1/decisions", json={"task": "zs", "text": f"hello {sentinel}"})
    client.post("/v1/feedback", json={**fb(), "text": f"hello {sentinel}"})
    client.post("/v1/feedback", json={**fb(label="other"), "text": f"hello {sentinel}"})
    client.post("/v1/decisions", json={"task": "zs", "text": f"{sentinel} " * 60})
    client.post("/v1/examples:batch", content=ndjson([{**fb(i=5), "text": sentinel},
                                                      f'{{"text": "{sentinel}"']),
                headers={"Content-Type": "application/x-ndjson"})
    assert caplog.records  # events were logged
    for rec in caplog.records:
        assert sentinel not in rec.getMessage()
