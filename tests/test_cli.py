import io
import json
import urllib.parse

import openpyxl
import pytest
from fastapi.testclient import TestClient

from decider import cli, sheets, tasks
from decider.backend.fake import FakeBackend
from decider.core import Decider
from decider.http import create_app
from decider.runner import InlineRunner

LABELS = ["Billing", "Support", "Sales"]
HEADER = ["Ticket ID", "Received", "Customer message", "Routed to"]


def sheet(n=60):
    wb = openpyxl.Workbook()
    wb.active.append(HEADER)
    for i in range(n):
        label = LABELS[i % 3]
        wb.active.append([f"SUP-{100 + i}", f"2026-09-{i % 28 + 1:02d}",
                          f"customer message number {i} about {label.lower()} things", label])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class Stdin:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)

    def isatty(self):
        return False

    def read(self):
        return self.buffer.read().decode()


def run(argv, stdin=None, monkeypatch=None):
    if stdin is not None:
        monkeypatch.setattr("sys.stdin", Stdin(stdin))
    cli.main(argv)


def test_guess_columns():
    rows = sheets.read(sheet())
    assert sheets.guess_columns(rows) == {"text": "Customer message", "label": "Routed to",
                                          "id": "Ticket ID"}


def test_guess_columns_without_labels():
    rows = [{"a": f"text {i}", "b": str(i)} for i in range(10)]
    with pytest.raises(sheets.SheetError, match="labels"):
        sheets.guess_columns(rows)


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DATA", tmp_path)
    monkeypatch.setattr(cli, "JOB", tmp_path / "cli-job.json")
    return tmp_path


def test_init_writes_a_zero_shot_task(data, monkeypatch, capsys):
    run(["init"], sheet(), monkeypatch)
    [spec] = tasks.load(data / "tasks.yaml")
    assert spec.name == "routed_to"
    assert spec.zero_shot
    assert set(spec.labels) == set(LABELS)
    assert "60 rows" in capsys.readouterr().err
    # Same sheet again is a no-op; a different one needs --force.
    run(["init"], sheet(), monkeypatch)
    with pytest.raises(SystemExit):
        run(["init", "--task", "other"], sheet(), monkeypatch)
    run(["init", "--task", "other", "--force"], sheet(), monkeypatch)
    assert tasks.load(data / "tasks.yaml")[0].name == "other"


@pytest.fixture
def service(data, monkeypatch):
    """`cli.call` goes to a real app on FakeBackend instead of localhost."""
    monkeypatch.setattr("sys.stdin", Stdin(sheet()))
    cli.main(["init"])
    d = Decider(tasks.load(data / "tasks.yaml"), backend=FakeBackend(), runner=InlineRunner(),
                db_path=data / "decider.db", model_dir=data / "models")
    client = TestClient(create_app(d, "k"))
    (data / "api_key").write_text("k\n")

    def call(method, path, body=None, ctype="application/json"):
        content = body if isinstance(body, bytes) or body is None else json.dumps(body)
        r = client.request(method, urllib.parse.quote(path, safe="/:?=&"), content=content,
                           headers={"Authorization": "Bearer k", "Content-Type": ctype})
        if r.status_code >= 400:
            raise cli.Fail(r.json()["error"]["message"])
        return r.json()

    monkeypatch.setattr(cli, "call", call)
    yield
    d.close()


def test_whole_flow(service, monkeypatch, capsys):
    run(["check"], sheet(), monkeypatch)
    out = capsys.readouterr().out
    assert "Model base on 60 rows" in out

    run(["import"], sheet(), monkeypatch)
    out = capsys.readouterr().out
    assert "60 added" in out and "ID column 'Ticket ID'" in out

    run(["train"])
    run(["wait"])
    out = capsys.readouterr().out
    assert "Trained routed_to-v1: verdict unverified" in out
    assert "decider-ai activate routed_to-v1" in out

    run(["activate"])
    assert "routed_to now serves routed_to-v1" in capsys.readouterr().out

    run(["about billing things"])
    assert capsys.readouterr().out.strip() in LABELS
    run(["--scores", "about billing things"])
    assert len(capsys.readouterr().out.strip().splitlines()) == 3

    run(["status"])
    assert "serving model routed_to-v1; 60 examples" in capsys.readouterr().out


def test_errors_are_one_line(service, monkeypatch, capsys):
    with pytest.raises(SystemExit) as e:
        run(["ask", "--task", "nope", "hi"])
    assert e.value.code == 1
    assert capsys.readouterr().err.startswith("decider-ai: no task 'nope'")
    with pytest.raises(SystemExit):
        run(["wait"])
    assert "run `decider-ai train`" in capsys.readouterr().err


def test_activate_waits_for_training(service, monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run(["activate"])
    assert "no trained model for routed_to yet" in capsys.readouterr().err
    run(["import"], sheet(), monkeypatch)
    run(["train"])
    capsys.readouterr()
    monkeypatch.setattr(cli, "last_job", lambda: {"task": "routed_to", "state": "running"})
    with pytest.raises(SystemExit):
        run(["activate"])
    assert "training is still running" in capsys.readouterr().err


def test_guide_names_the_image(monkeypatch, capsys):
    monkeypatch.setenv("DECIDER_IMAGE", "ghcr.io/x/decider-ai:v9")
    cli.main(["guide"])
    out = capsys.readouterr().out
    assert "docker run --rm -i -v decider-data:/data ghcr.io/x/decider-ai:v9 init < FILE" in out
    assert "{image}" not in out


def test_bare_command_shows_help_not_a_second_server(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code == 0
    assert "usage: decider-ai" in capsys.readouterr().out
