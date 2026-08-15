"""Session-attributed unresolved finding state for PostToolUse/Stop hooks."""

import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager

from _hooklib import ext
from _markers import marker_counts


STALE_SECONDS = 7 * 24 * 60 * 60


def _root():
    return os.environ.get(
        "MAINFRAME_MARKER_STATE_DIR",
        os.path.join(tempfile.gettempdir(), "mainframe-codex-marker-state"),
    )


def _key(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _namespace_prefix(namespace):
    return "" if namespace == "markers" else f"{_key(namespace)}-"


def _path(session_id, agent_id, namespace="markers"):
    name = f"{_namespace_prefix(namespace)}{_key(session_id)}-{_key(agent_id or 'main')}.json"
    return os.path.join(_root(), name)


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
        raise TimeoutError("marker state lock unavailable")
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
        if not isinstance(value, dict) or not isinstance(value.get("files", {}), dict):
            raise ValueError("invalid marker state")
        return value
    except FileNotFoundError:
        return {"files": {}}


def _save(path, state):
    files = state.get("files") or {}
    if not files:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        return
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".markers-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"files": files}, handle, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _current_counts(file_path, counter):
    try:
        with open(file_path, encoding="utf-8", errors="replace") as handle:
            return counter(handle.read(), ext(file_path), file_path)
    except FileNotFoundError:
        return {}


def _revalidate(state, counter, current_overrides=None):
    files = state.get("files") or {}
    for file_path in list(files):
        current = ((current_overrides or {}).get(file_path)
                   if file_path in (current_overrides or {})
                   else _current_counts(file_path, counter))
        labels = files[file_path]
        for label, baseline in list(labels.items()):
            if current.get(label, 0) <= int(baseline):
                del labels[label]
        if not labels:
            del files[file_path]
    state["files"] = files


def _revalidate_file(state, file_path, counter, current_counts=None):
    """Revalidate only the file involved in the current PostToolUse event."""
    files = state.get("files") or {}
    labels = files.get(file_path)
    if not labels:
        state["files"] = files
        return
    current = (dict(current_counts) if current_counts is not None
               else _current_counts(file_path, counter))
    for label, baseline in list(labels.items()):
        if current.get(label, 0) <= int(baseline):
            del labels[label]
    if not labels:
        files.pop(file_path, None)
    state["files"] = files


def update(session_id, agent_id, file_path, deltas, *, counter=marker_counts,
           namespace="markers", current_counts=None, session_wide=False):
    """Record one file and return (new, active, resolved) owned labels."""
    if not session_id:
        raise ValueError("marker state requires session_id")
    file_path = os.path.realpath(file_path)
    path = _path(session_id, agent_id, namespace)
    with _lock(path):
        state = _load(path)
        if session_wide:
            previously_owned = {
                label
                for labels in (state.get("files") or {}).values()
                for label in labels
            }
        else:
            previously_owned = set(
                (state.get("files") or {}).get(file_path, {})
            )
        _revalidate_file(state, file_path, counter, current_counts)
        current = (dict(current_counts) if current_counts is not None
                   else _current_counts(file_path, counter))
        labels = state["files"].setdefault(file_path, {})
        for label, delta in deltas.items():
            if delta > 0 and label not in labels:
                labels[label] = max(0, current.get(label, 0) - int(delta))
        if not labels:
            state["files"].pop(file_path, None)
        if session_wide:
            active = {
                label
                for owned in state["files"].values()
                for label in owned
            }
        else:
            active = set(state["files"].get(file_path, {}))
        _save(path, state)
        return (sorted(active - previously_owned), sorted(active),
                sorted(previously_owned - active))


def unresolved(session_id, agent_id=None, include_subagents=False, *,
               counter=marker_counts, namespace="markers", include_files=False,
               include_details=False):
    """Return unresolved labels after re-reading files; persist resolutions."""
    root = _root()
    prefix = _namespace_prefix(namespace) + _key(session_id) + "-"
    if include_subagents:
        try:
            paths = [os.path.join(root, name) for name in os.listdir(root)
                     if name.startswith(prefix) and name.endswith(".json")]
        except FileNotFoundError:
            paths = []
    else:
        paths = [_path(session_id, agent_id, namespace)]
    labels = set()
    files = set()
    details = {}
    for path in paths:
        with _lock(path):
            state = _load(path)
            _revalidate(state, counter)
            for file_path, entries in state.get("files", {}).items():
                labels.update(entries)
                files.add(file_path)
                merged = details.setdefault(file_path, {})
                for label, baseline in entries.items():
                    baseline = int(baseline)
                    merged[label] = min(merged.get(label, baseline), baseline)
            _save(path, state)
    _cleanup_stale()
    if include_details:
        return details
    result = sorted(labels)
    return (result, sorted(files)) if include_files else result


def _cleanup_stale():
    root = _root()
    try:
        names = os.listdir(root)
    except FileNotFoundError:
        return
    cutoff = time.time() - STALE_SECONDS
    for name in names:
        path = os.path.join(root, name)
        try:
            if os.path.getmtime(path) < cutoff:
                if name.endswith(".lock"):
                    os.rmdir(path)
                elif name.endswith(".json"):
                    os.unlink(path)
        except (FileNotFoundError, OSError):
            continue
