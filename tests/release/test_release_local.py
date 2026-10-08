"""Runs the release-test steps in-process (FakeBackend, InlineRunner) so their logic is proven in CI.

Restart is simulated by closing the ``Decider`` and opening a new one on the same files.
"""

from fastapi.testclient import TestClient
from release_test import NZ, run_release

from decider.backend.fake import FakeBackend
from decider.core import Decider
from decider.http import create_app
from decider.runner import InlineRunner
from decider.tasks import load

TASKS = load(__file__.replace("test_release_local.py", "tasks.yaml"))
KEY = "release-key"


class Server:
    """An authenticated client whose ``Decider`` can be restarted on the same files."""

    def __init__(self, tmp_path):
        self.tmp_path, self.decider = tmp_path, None
        self.restart()

    def restart(self):
        if self.decider is not None:
            self.decider.close()
        self.decider = Decider(TASKS, backend=FakeBackend(), runner=InlineRunner(),
                               db_path=self.tmp_path / "decider.db",
                               model_dir=self.tmp_path / "models")
        self.client = TestClient(create_app(self.decider, KEY))
        self.client.headers.update({"Authorization": f"Bearer {KEY}"})

    def __getattr__(self, name):  # get, post, delete
        return getattr(self.client, name)


def records():
    labels = list(TASKS[1].labels)
    return [{"task": NZ, "text": f"anfrage nummer {i} zu {labels[i % 18]}",
             "label": labels[i % 18], "external_id": f"rec-{i}", "group_id": f"rec-{i}"}
            for i in range(200)]


def test_release_steps_in_process(tmp_path):
    server = Server(tmp_path)
    try:
        run_release(server, records(), server.restart)
    finally:
        server.decider.close()
