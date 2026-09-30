"""Private bounded state for the Antigravity hook transport."""

from __future__ import annotations

from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import time


EVENT_TTL = 7 * 24 * 60 * 60


def _database(state: Path) -> Path | None:
    if state.is_symlink():
        return None
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    state.chmod(0o700)
    metadata = state.stat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        return None
    database = state / "events.sqlite3"
    if database.is_symlink():
        return None
    descriptor = os.open(database, os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.close(descriptor)
    return database


def open_state(state: Path):
    database = _database(state)
    if database is None:
        return None
    connection = sqlite3.connect(database, timeout=0.2)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, expires REAL)")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS findings (scope TEXT, path TEXT, fingerprint TEXT, "
        "baseline INTEGER, label TEXT, expires REAL, PRIMARY KEY(scope,path,fingerprint))"
    )
    now = time.time()
    connection.execute("DELETE FROM events WHERE expires <= ?", (now,))
    connection.execute("DELETE FROM findings WHERE expires <= ?", (now,))
    return connection


def claim_event(state: Path, identity: str) -> bool:
    key = hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()
    connection = open_state(state)
    if connection is None:
        return False
    with closing(connection), connection:
        try:
            connection.execute("INSERT INTO events VALUES (?, ?)", (key, time.time() + EVENT_TTL))
        except sqlite3.IntegrityError:
            return False
    return True
