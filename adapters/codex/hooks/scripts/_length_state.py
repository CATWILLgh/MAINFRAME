"""Two-phase session baselines for the delta-aware length quality hook."""

import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager

from _hooklib import ext
from _length_check import FILE_LENGTH_EXTENSIONS, count_lines, python_function_spans


STALE_SECONDS = 7 * 24 * 60 * 60
PYTHON_EXTENSIONS = frozenset({".py", ".pyi"})


def _root():
    return os.environ.get(
        "MAINFRAME_LENGTH_STATE_DIR",
        os.path.join(tempfile.gettempdir(), "mainframe-codex-length-state"),
    )


def _key(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _path(session_id, agent_id):
    return os.path.join(
        _root(), f"{_key(session_id)}-{_key(agent_id or 'main')}.json"
    )


@contextmanager
def _lock(path):
    lock = path + ".lock"
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    for _ in range(100):
        try:
            os.mkdir(lock, mode=0o700)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock) > 60:
                    os.rmdir(lock)
                    continue
            except FileNotFoundError:
                continue
            time.sleep(0.01)
    else:
        raise TimeoutError("length state lock unavailable")
    try:
        yield
    finally:
        try:
            os.rmdir(lock)
        except FileNotFoundError:
            pass


def _load(path):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError("invalid length state")
        if not isinstance(value.get("files", {}), dict):
            raise ValueError("invalid length files")
        if not isinstance(value.get("pending", {}), dict):
            raise ValueError("invalid length pending state")
        return value
    except FileNotFoundError:
        return {"files": {}, "pending": {}}


def _save(path, state):
    files = state.get("files") or {}
    pending = state.get("pending") or {}
    if not files and not pending:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        return
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".length-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                {"files": files, "pending": pending}, handle,
                separators=(",", ":"),
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _snapshot(file_path):
    try:
        with open(file_path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except FileNotFoundError:
        text = ""
    functions = None
    if ext(file_path) in PYTHON_EXTENSIONS:
        try:
            functions = {
                name: end - start + 1
                for name, start, end in python_function_spans(text)
            }
        except SyntaxError:
            functions = None
    return {
        "path": os.path.realpath(file_path),
        "lines": count_lines(text),
        "functions": functions,
        "captured_ns": time.time_ns(),
    }


def capture(payload):
    """Capture a pending baseline before an Edit/Write/MultiEdit call."""
    session_id = payload.get("session_id")
    tool_use_id = payload.get("tool_use_id")
    if not session_id or not tool_use_id:
        raise ValueError("length baseline requires session_id and tool_use_id")
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if file_path and not os.path.isabs(file_path):
        file_path = os.path.join(payload.get("cwd") or ".", file_path)
    if ext(file_path) not in FILE_LENGTH_EXTENSIONS:
        return
    path = _path(session_id, payload.get("agent_id"))
    with _lock(path):
        state = _load(path)
        state["pending"][tool_use_id] = _snapshot(file_path)
        _save(path, state)
    _cleanup_stale()


def confirm(payload):
    """Promote a PreToolUse baseline only after the edit completed."""
    session_id = payload.get("session_id")
    tool_use_id = payload.get("tool_use_id")
    if not session_id or not tool_use_id:
        raise ValueError("length confirmation requires session_id and tool_use_id")
    path = _path(session_id, payload.get("agent_id"))
    with _lock(path):
        state = _load(path)
        snapshot = state["pending"].pop(tool_use_id, None)
        if snapshot is not None:
            state["files"].setdefault(snapshot["path"], snapshot)
        _save(path, state)


def _state_paths(session_id, include_subagents):
    if not include_subagents:
        return [_path(session_id, None)]
    prefix = _key(session_id) + "-"
    try:
        return [
            os.path.join(_root(), name) for name in os.listdir(_root())
            if name.startswith(prefix) and name.endswith(".json")
        ]
    except FileNotFoundError:
        return []


def baselines(session_id, include_subagents=True):
    """Return the earliest confirmed baseline for each file in the session."""
    merged = {}
    for path in _state_paths(session_id, include_subagents):
        with _lock(path):
            state = _load(path)
        for file_path, snapshot in state.get("files", {}).items():
            existing = merged.get(file_path)
            if (existing is None
                    or int(snapshot.get("captured_ns") or 0)
                    < int(existing.get("captured_ns") or 0)):
                merged[file_path] = snapshot
    return merged


def clear(session_id, include_subagents=True):
    for path in _state_paths(session_id, include_subagents):
        with _lock(path):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def _cleanup_stale():
    try:
        names = os.listdir(_root())
    except FileNotFoundError:
        return
    cutoff = time.time() - STALE_SECONDS
    for name in names:
        path = os.path.join(_root(), name)
        try:
            if os.path.getmtime(path) >= cutoff:
                continue
            if name.endswith(".lock"):
                os.rmdir(path)
            elif name.endswith(".json"):
                os.unlink(path)
        except (FileNotFoundError, OSError):
            continue
