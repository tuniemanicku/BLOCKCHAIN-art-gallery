"""Persistent state of ONE node, kept in that node's own SQLite file.

Tables:
  meta    - consensus variables that must survive a restart (term, vote, commit index)
  blocks  - this node's copy of the blockchain (the replicated log)
  assets  - read-only snapshot of the committed asset state, refreshed after each
            commit so it can be inspected with any SQLite browser. It is derived
            from `blocks` and is never used as the source of truth.
"""

import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blocks (
    idx       INTEGER PRIMARY KEY,
    term      INTEGER NOT NULL,
    hash      TEXT    NOT NULL,
    prev_hash TEXT    NOT NULL,
    kind      TEXT    NOT NULL,
    body      TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
    asset_id    TEXT PRIMARY KEY,
    title       TEXT,
    author      TEXT,
    accepted_on TEXT,
    price       INTEGER,
    owner       TEXT,
    owner_name  TEXT,
    status      TEXT,
    version     INTEGER
);
"""


class NodeStorage:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    # --- meta -------------------------------------------------------------
    def get_meta(self, key: str, default=None):
        row = self._db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_meta(self, **values) -> None:
        with self._lock, self._db:
            for key, value in values.items():
                self._db.execute(
                    "INSERT INTO meta(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, json.dumps(value)),
                )

    # --- blocks -----------------------------------------------------------
    def load_blocks(self) -> list:
        rows = self._db.execute("SELECT body FROM blocks ORDER BY idx").fetchall()
        return [json.loads(row[0]) for row in rows]

    def append_blocks(self, blocks: list) -> None:
        with self._lock, self._db:
            self._db.executemany(
                "INSERT INTO blocks(idx, term, hash, prev_hash, kind, body) VALUES(?, ?, ?, ?, ?, ?)",
                [(b["index"], b["term"], b["hash"], b["prev_hash"], b["kind"], json.dumps(b))
                 for b in blocks],
            )

    def truncate_from(self, index: int) -> None:
        """Remove blocks with idx >= index (uncommitted entries that lost a conflict)."""
        with self._lock, self._db:
            self._db.execute("DELETE FROM blocks WHERE idx >= ?", (index,))

    # --- asset snapshot ---------------------------------------------------
    def save_asset_snapshot(self, assets: list) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM assets")
            self._db.executemany(
                "INSERT INTO assets VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(a["asset_id"], a["title"], a["author"], a["accepted_on"], a["price"],
                  a["owner"], a["owner_name"], a["status"], a["version"]) for a in assets],
            )

    def close(self) -> None:
        self._db.close()
