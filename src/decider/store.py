"""SQLite storage for ``Decider``. Internal: only ``core`` uses it.

One connection, guarded by the caller's lock. ``secure_delete`` is on so erased
rows are zeroed in the file; ``forget`` truncates the WAL afterwards.

Tables T2.4 fills (``model_versions``, ``version_examples``, ``splits``,
``split_members``, ``active``, ``jobs``) are created now so later slices only
add code, not migrations.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    name           TEXT PRIMARY KEY,
    label_set_hash TEXT NOT NULL,
    labels         TEXT NOT NULL            -- JSON list of label names
);

-- Confirmed examples: the only stored message text.
CREATE TABLE IF NOT EXISTS examples (
    id          INTEGER PRIMARY KEY,
    task        TEXT NOT NULL,
    external_id TEXT NOT NULL,
    text        TEXT NOT NULL,
    label       TEXT NOT NULL,
    group_id    TEXT,
    label_mode  TEXT NOT NULL,              -- 'blind' | 'assisted'
    request_id  TEXT,                       -- opaque link to a served decision
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    UNIQUE (task, external_id)
);
CREATE INDEX IF NOT EXISTS examples_external_id ON examples (external_id);

-- Trained model versions (T2.4). Version IDs are globally unique.
CREATE TABLE IF NOT EXISTS model_versions (
    version        TEXT PRIMARY KEY,
    task           TEXT NOT NULL,
    path           TEXT,
    seed           INTEGER,
    created_at     REAL NOT NULL,
    verdict        TEXT,                    -- recommended | not_recommended | unverified
    metrics        TEXT,                    -- JSON
    split_revision INTEGER,
    split_size     INTEGER
);

-- External IDs each version was trained on (kept after forget, to count erasures).
CREATE TABLE IF NOT EXISTS version_examples (
    version     TEXT NOT NULL,
    external_id TEXT NOT NULL,
    erased      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (version, external_id)
);

-- Frozen splits (T2.4): one row per revision; the highest revision is current.
CREATE TABLE IF NOT EXISTS splits (
    task       TEXT NOT NULL,
    revision   INTEGER NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (task, revision)
);
CREATE TABLE IF NOT EXISTS split_members (
    task        TEXT NOT NULL,
    revision    INTEGER NOT NULL,
    external_id TEXT NOT NULL,
    PRIMARY KEY (task, revision, external_id)
);

-- Active model pointer per task (T2.4).
CREATE TABLE IF NOT EXISTS active (
    task    TEXT PRIMARY KEY,
    version TEXT NOT NULL
);

-- Retrain jobs (T2.4).
CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    task          TEXT NOT NULL,
    state         TEXT NOT NULL,            -- running | succeeded | failed
    progress      REAL NOT NULL DEFAULT 0,
    epoch         INTEGER,                  -- epochs done; NULL when the backend does not say
    epochs        INTEGER,                  -- total epochs; NULL when the backend does not say
    refresh_split INTEGER NOT NULL DEFAULT 0,
    version       TEXT,
    error         TEXT,
    created_at    REAL NOT NULL,
    finished_at   REAL
);
"""


class Store:
    def __init__(self, db_path: str | Path) -> None:
        self.db = sqlite3.connect(str(db_path), check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        # Databases created before jobs.epoch/epochs existed.
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(jobs)")}
        for col in ("epoch", "epochs"):
            if col not in cols:
                self.db.execute(f"ALTER TABLE jobs ADD COLUMN {col} INTEGER")

    def close(self) -> None:
        self.db.close()

    # --- tasks ---------------------------------------------------------------

    def task_hash(self, name: str) -> str | None:
        row = self.db.execute("SELECT label_set_hash FROM tasks WHERE name=?", (name,)).fetchone()
        return row[0] if row else None

    def put_task(self, name: str, label_set_hash: str, labels: list[str]) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO tasks (name, label_set_hash, labels) VALUES (?, ?, ?)",
            (name, label_set_hash, json.dumps(labels)),
        )

    # --- examples ------------------------------------------------------------

    def upsert_example(
        self,
        task: str,
        external_id: str,
        text: str,
        label: str,
        group_id: str | None,
        label_mode: str,
        request_id: str | None,
        now: float,
    ) -> bool:
        """Insert or update one example; returns True when it was new."""
        exists = self.db.execute(
            "SELECT 1 FROM examples WHERE task=? AND external_id=?", (task, external_id)
        ).fetchone()
        self.db.execute(
            """INSERT INTO examples (task, external_id, text, label, group_id, label_mode,
                                     request_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (task, external_id) DO UPDATE SET
                   text=excluded.text, label=excluded.label, group_id=excluded.group_id,
                   label_mode=excluded.label_mode, request_id=excluded.request_id,
                   updated_at=excluded.updated_at""",
            (task, external_id, text, label, group_id, label_mode, request_id, now, now),
        )
        return exists is None

    def label_counts(self, task: str) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT label, COUNT(*) FROM examples WHERE task=? GROUP BY label", (task,)
        )
        return dict(rows.fetchall())

    def active_version(self, task: str) -> tuple[str, str | None] | None:
        row = self.db.execute(
            """SELECT a.version, v.path FROM active a
               LEFT JOIN model_versions v ON v.version = a.version WHERE a.task=?""",
            (task,),
        ).fetchone()
        return (row[0], row[1]) if row else None

    def forget(self, external_id: str) -> tuple[int, int, list[str]]:
        """Hard-delete every example with this ID; returns (examples, split members, versions)."""
        with self.db:  # one transaction
            self.db.execute("BEGIN")
            n = self.db.execute(
                "DELETE FROM examples WHERE external_id=?", (external_id,)
            ).rowcount
            # Only members of each task's current revision count as removed from the split.
            m = self.db.execute(
                """DELETE FROM split_members WHERE external_id=? AND revision = (
                       SELECT MAX(revision) FROM splits s WHERE s.task = split_members.task)""",
                (external_id,),
            ).rowcount
            versions = [
                r[0]
                for r in self.db.execute(
                    "SELECT version FROM version_examples WHERE external_id=? ORDER BY version",
                    (external_id,),
                )
            ]
            self.db.execute(
                "UPDATE version_examples SET erased=1 WHERE external_id=?", (external_id,)
            )
        self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return n, m, versions
