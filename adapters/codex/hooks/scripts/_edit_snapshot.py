"""Short-lived, tool-call-attributed source snapshots for edit checks."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


MAX_FILE_BYTES = 2_000_000
MAX_FILES = 24
SNAPSHOT_MAX_AGE = 60 * 60

_PATCH_PATH = re.compile(
    r"^\*\*\* (?:Add|Update|Delete) File:\s*(.+?)\s*$", re.MULTILINE
)
_MOVE_PATH = re.compile(r"^\*\*\* Move to:\s*(.+?)\s*$", re.MULTILINE)


def identity(payload: dict) -> str:
    fields = (
        payload.get("session_id"), payload.get("turn_id"),
        payload.get("agent_id") or "main", payload.get("tool_use_id"),
    )
    if not fields[0] or not fields[3]:
        raise ValueError("edit hook requires session_id and tool_use_id")
    raw = "\0".join(str(value or "") for value in fields).encode()
    return hashlib.sha256(raw).hexdigest()


def snapshot_root() -> Path:
    override = os.environ.get("MAINFRAME_CODEX_SNAPSHOT_DIR")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "mainframe-codex-snapshots"


def snapshot_path(payload: dict) -> Path:
    return snapshot_root() / f"{identity(payload)}.json"


def cleanup() -> None:
    try:
        entries = list(snapshot_root().iterdir())
    except FileNotFoundError:
        return
    cutoff = time.time() - SNAPSHOT_MAX_AGE
    for path in entries:
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


def atomic_write(payload: dict, files: list[dict]) -> None:
    path = snapshot_path(payload)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".snapshot-", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"files": files}, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def consume(payload: dict) -> list[dict]:
    path = snapshot_path(payload)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        files = value.get("files") if isinstance(value, dict) else None
        if not isinstance(files, list):
            raise ValueError("invalid edit snapshot")
        return files
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def project_root(cwd: Path) -> Path:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=cwd,
            stderr=subprocess.DEVNULL, timeout=2,
        ).decode().strip()
        return Path(value).resolve() if value else cwd
    except (OSError, subprocess.SubprocessError):
        return cwd


def paths(payload: dict) -> list[Path]:
    tool_input = payload.get("tool_input") or {}
    cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    project = project_root(cwd)
    raw = [
        value for key in ("file_path", "path")
        if isinstance((value := tool_input.get(key)), str) and value
    ]
    patch = next(
        (
            value for key in ("patch", "command", "input")
            if isinstance((value := tool_input.get(key)), str) and "*** " in value
        ),
        "",
    )
    raw.extend(_PATCH_PATH.findall(patch))
    raw.extend(_MOVE_PATH.findall(patch))
    result = []
    for value in raw:
        candidate = Path(value).expanduser()
        candidate = (
            candidate if candidate.is_absolute() else cwd / candidate
        ).resolve()
        try:
            candidate.relative_to(project)
        except ValueError:
            continue
        if candidate not in result:
            result.append(candidate)
    return result[:MAX_FILES]


def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except OSError:
        return None


def edits(before: str, after: str) -> list[dict[str, str]]:
    old = before.splitlines(keepends=True)
    new = after.splitlines(keepends=True)
    result = []
    for tag, first_old, last_old, first_new, last_new in difflib.SequenceMatcher(
        None, old, new, autojunk=False
    ).get_opcodes():
        if tag != "equal":
            result.append({
                "old_string": "".join(old[first_old:last_old]),
                "new_string": "".join(new[first_new:last_new]),
            })
    return result
