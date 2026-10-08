"""The ``Runner`` port: where a retrain job's work runs.

``Decider`` owns the one-job-at-a-time rule; a runner only executes work.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Callable, Protocol

Work = Callable[[], None]


class Runner(Protocol):
    def start(self, work: Work) -> None: ...


class InlineRunner:
    """Runs the work immediately, in the caller's thread (tests, HTTP tests)."""

    def start(self, work: Work) -> None:
        work()


class ManualRunner:
    """Holds work until ``release()``, so tests can observe a running job."""

    def __init__(self) -> None:
        self.held: list[Work] = []

    def start(self, work: Work) -> None:
        self.held.append(work)

    def release(self) -> None:
        while self.held:
            self.held.pop(0)()


class ThreadRunner:
    """Runs work in a background daemon thread at ``nice`` priority.

    ``threads`` caps the training threads (default: half the CPUs); it is applied
    to torch when torch is loaded.
    """

    def __init__(self, nice: int = 10, threads: int | None = None) -> None:
        self.nice = nice
        self.threads = threads or max(1, (os.cpu_count() or 2) // 2)
        self.thread: threading.Thread | None = None

    def start(self, work: Work) -> None:
        def run() -> None:
            try:  # per-thread on Linux
                tid = threading.get_native_id()
                os.setpriority(os.PRIO_PROCESS, tid, os.getpriority(os.PRIO_PROCESS, tid) + self.nice)
            except (AttributeError, OSError):
                pass
            torch = sys.modules.get("torch")
            if torch is not None:
                torch.set_num_threads(self.threads)
            work()

        self.thread = threading.Thread(target=run, name="decider-train", daemon=True)
        self.thread.start()

    def join(self, timeout: float | None = None) -> None:
        if self.thread is not None:
            self.thread.join(timeout)
