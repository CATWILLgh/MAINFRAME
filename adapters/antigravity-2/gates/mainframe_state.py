#!/usr/bin/env python3
"""Bounded local state primitives for the Antigravity hook bridge."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path


STATE_TTL_SECONDS = 24 * 60 * 60
MAX_STATE_FILES = 32


def prune_state_directory(
    directory: Path,
    *,
    ttl_seconds: int = STATE_TTL_SECONDS,
    max_files: int = MAX_STATE_FILES,
    now: float | None = None,
) -> None:
    try:
        entries = []
        for path in directory.iterdir():
            if not (path.is_file() or path.is_symlink()):
                continue
            try:
                entries.append((path.lstat().st_mtime, path))
            except OSError:
                continue
    except OSError:
        return
    current = time.time() if now is None else now
    for index, (modified, path) in enumerate(sorted(entries, reverse=True)):
        if current - modified <= ttl_seconds and index < max_files:
            continue
        try:
            path.unlink()
        except OSError:
            pass


def atomic_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prune_state_directory(path.parent, max_files=MAX_STATE_FILES - 1)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump(data, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


def read_json(path: Path, fallback: object) -> object:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return fallback
