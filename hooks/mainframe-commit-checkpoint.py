#!/usr/bin/env python3
"""Bounded post-edit checkpoint advice; never execute Git mutations or block.

Retain only expiring hashes, counters and timestamps. Successful edit evidence
and native recipient identity are supplied by the adapter. Read Git identity to
reset after a new HEAD; do not scan file bodies or infer completed work.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import time

EDIT_THRESHOLD = 25
LINE_THRESHOLD = 2000
COOLDOWN_SECONDS = 600
TTL_SECONDS = 6 * 60 * 60
MAX_EVENTS = 4096
MAX_SCOPES = 128

MESSAGE = (
    "Commit checkpoint: substantial editing has accumulated since the last observed Git HEAD. "
    "At the next coherent boundary, verify the completed part and make a local Conventional "
    "Commit if your task/project permits it: <type>(<scope>): <summary> (scope optional). "
    "Commit only your intended changes; preserve unrelated work and do not push. "
    "Do not commit unfinished work merely to satisfy this reminder."
)


def text_lines(*texts: str) -> int:
    """Estimate touched text volume without keeping content or computing a diff."""
    return min(100_000, sum(text.count("\n") + int(bool(text) and not text.endswith("\n"))
                            for text in texts if isinstance(text, str)))


def _git_identity(workspace: str) -> tuple[str, str] | None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    def git(*args):
        result = subprocess.run(["git", "-C", workspace, *args], env=env,
                                capture_output=True, text=True, timeout=1, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    root = git("rev-parse", "--show-toplevel")
    if not root:
        return None
    head = git("rev-parse", "--verify", "HEAD")
    if head is None:
        branch = git("symbolic-ref", "HEAD")
        if not branch:
            return None
        head = "unborn:" + branch
    return str(Path(root).resolve()), head


def _has_changes(workspace: str) -> bool | None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    result = subprocess.run(["git", "-C", workspace, "status", "--porcelain", "--untracked-files=normal"],
                            env=env, capture_output=True, timeout=1, check=False)
    return bool(result.stdout) if result.returncode == 0 else None


def observe(scope: str, workspace: str, event_id: str, changed_lines: int = 0,
            *, state_root: Path) -> str | None:
    """Observe one successful native edit. Failure is neutral and creates no advice."""
    if (not all(isinstance(value, str) and 0 < len(value) <= 4096
                for value in (scope, workspace, event_id))
            or not Path(workspace).is_absolute()
            or not isinstance(changed_lines, int) or isinstance(changed_lines, bool)
            or not 0 <= changed_lines <= 100_000):
        return None
    try:
        identity = _git_identity(workspace)
        if identity is None:
            return None
        root, head = identity
        state = Path(state_root)
        if Path(state_root).is_symlink() or state.is_symlink():
            return None
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
        if state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
            return None
        database = state / "commit-checkpoint.sqlite3"
        if database.is_symlink():
            return None
        fd = os.open(database, os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as stream:
            metadata = os.fstat(stream.fileno())
            if (metadata.st_uid != os.getuid() or metadata.st_mode & 0o077
                    or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1):
                return None
        key = hashlib.sha256((scope + "\0" + root).encode()).hexdigest()
        event_key = hashlib.sha256((key + "\0" + event_id).encode()).hexdigest()
        head_key = hashlib.sha256(head.encode()).hexdigest()
        now = time.time()
        with closing(sqlite3.connect(database, timeout=0.2)) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS counters "
                               "(scope TEXT PRIMARY KEY, head TEXT, edits INTEGER, lines INTEGER, warned REAL, expires REAL)")
            connection.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, expires REAL)")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM events WHERE expires <= ?", (now,))
            connection.execute("DELETE FROM counters WHERE expires <= ?", (now,))
            if connection.execute("SELECT 1 FROM events WHERE id=?", (event_key,)).fetchone():
                return None
            if connection.execute("SELECT count(*) FROM events").fetchone()[0] >= MAX_EVENTS:
                return None
            row = connection.execute("SELECT head, edits, lines, warned FROM counters WHERE scope=?", (key,)).fetchone()
            if row is None and connection.execute("SELECT count(*) FROM counters").fetchone()[0] >= MAX_SCOPES:
                return None
            edits, lines, warned = row[1:] if row and row[0] == head_key else (0, 0, None)
            edits, lines = min(edits + 1, 1_000_000), min(lines + changed_lines, 1_000_000)
            due = (edits >= EDIT_THRESHOLD or lines >= LINE_THRESHOLD)
            due = due and (warned is None or now - warned >= COOLDOWN_SECONDS)
            clean = False
            if due:
                changes = _has_changes(root)
                clean = changes is False
                due = changes is True
            connection.execute("INSERT INTO events VALUES (?, ?)", (event_key, now + TTL_SECONDS))
            connection.execute("INSERT OR REPLACE INTO counters VALUES (?, ?, ?, ?, ?, ?)",
                               (key, head_key, 0 if due or clean else edits, 0 if due or clean else lines,
                                now if due else warned, now + TTL_SECONDS))
            return MESSAGE if due else None
    except (OSError, RuntimeError, sqlite3.Error, subprocess.SubprocessError, UnicodeError):
        return None
