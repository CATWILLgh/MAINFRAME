"""Session-attributed changed-line state for the Fallow quality hook."""

import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager


STALE_SECONDS = 7 * 24 * 60 * 60
JS_EXTENSIONS = frozenset({
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte",
})


def _root():
    return os.environ.get(
        "MAINFRAME_FALLOW_STATE_DIR",
        os.path.join(tempfile.gettempdir(), "mainframe-codex-fallow-state"),
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
        raise TimeoutError("Fallow state lock unavailable")
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
        if not isinstance(value, dict) or not isinstance(value.get("files"), dict):
            raise ValueError("invalid Fallow state")
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
    fd, temporary = tempfile.mkstemp(prefix=".fallow-", dir=directory, text=True)
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


def _digest(line):
    return hashlib.sha256(line.encode("utf-8", "replace")).hexdigest()[:20]


def _matching_spans(text, value):
    if not value:
        return []
    spans = []
    start = 0
    while True:
        index = text.find(value, start)
        if index < 0:
            return spans
        first = text.count("\n", 0, index) + 1
        last = first + value.count("\n")
        spans.append((first, last))
        start = index + max(1, len(value))


def _tool_spans(tool_name, tool_input, text):
    if tool_name == "Write":
        return [(1, max(1, text.count("\n") + 1))]
    if tool_name == "Edit":
        spans = _matching_spans(text, tool_input.get("new_string", "") or "")
        if tool_input.get("replace_all") or len(spans) <= 1:
            return spans
        return []
    if tool_name == "MultiEdit":
        spans = []
        for edit in tool_input.get("edits", []) or []:
            matches = _matching_spans(text, edit.get("new_string", "") or "")
            if edit.get("replace_all") or len(matches) <= 1:
                spans.extend(matches)
        return spans
    return []


def _is_deletion(tool_name, tool_input):
    if tool_name == "Edit":
        return bool(tool_input.get("old_string")) and not tool_input.get("new_string")
    if tool_name == "MultiEdit":
        return any(
            edit.get("old_string") and not edit.get("new_string")
            for edit in (tool_input.get("edits") or [])
        )
    return False


def record(payload):
    """Record successful lines written by one PostToolUse call, without source."""
    session_id = payload.get("session_id")
    if not session_id:
        raise ValueError("Fallow state requires session_id")
    tool_name = payload.get("tool_name") or ""
    if tool_name not in ("Edit", "MultiEdit", "Write"):
        return
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    suffix = os.path.splitext(file_path)[1].lower()
    if suffix not in JS_EXTENSIONS or not os.path.isfile(file_path):
        return
    file_path = os.path.realpath(file_path)
    with open(file_path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    spans = _tool_spans(tool_name, tool_input, text)
    deletion = _is_deletion(tool_name, tool_input)
    if not spans and not deletion:
        return
    lines = text.splitlines()
    records = []
    for first, last in spans:
        for number in range(first, min(last, len(lines)) + 1):
            line = lines[number - 1]
            if line.strip():
                records.append({"line": number, "digest": _digest(line)})
    path = _path(session_id, payload.get("agent_id"))
    with _lock(path):
        state = _load(path)
        entry = state["files"].setdefault(
            file_path, {"whole": False, "deletion": False, "lines": []}
        )
        entry["whole"] = bool(entry.get("whole") or tool_name == "Write")
        entry["deletion"] = bool(entry.get("deletion") or deletion)
        known = {(item.get("line"), item.get("digest")) for item in entry["lines"]}
        entry["lines"].extend(
            item for item in records
            if (item["line"], item["digest"]) not in known
        )
        _save(path, state)
    _cleanup_stale()


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


def _merge_states(paths):
    merged = {}
    for path in paths:
        with _lock(path):
            state = _load(path)
        for file_path, incoming in state.get("files", {}).items():
            entry = merged.setdefault(
                file_path, {"whole": False, "deletion": False, "lines": []}
            )
            entry["whole"] = bool(entry["whole"] or incoming.get("whole"))
            entry["deletion"] = bool(entry["deletion"] or incoming.get("deletion"))
            entry["lines"].extend(incoming.get("lines") or [])
    return merged


def _current_lines(entry, lines):
    if entry.get("whole"):
        return list(range(1, len(lines) + 1))
    by_digest = {}
    for number, line in enumerate(lines, 1):
        by_digest.setdefault(_digest(line), []).append(number)
    owned = set()
    for item in entry.get("lines") or []:
        expected = int(item.get("line") or 0)
        digest = item.get("digest")
        if 1 <= expected <= len(lines) and _digest(lines[expected - 1]) == digest:
            owned.add(expected)
            continue
        matches = by_digest.get(digest) or []
        if len(matches) == 1:
            owned.add(matches[0])
    return sorted(owned)


def _ranges(numbers):
    if not numbers:
        return []
    result = []
    first = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        result.append((first, previous))
        first = previous = number
    result.append((first, previous))
    return result


def build_diff(session_id, cwd, include_subagents=True):
    """Build a valid diff whose new-side hunks contain only owned live lines."""
    root = os.path.realpath(cwd)
    chunks = []
    for file_path, entry in sorted(
        _merge_states(_state_paths(session_id, include_subagents)).items()
    ):
        real = os.path.realpath(file_path)
        try:
            if os.path.commonpath((root, real)) != root or not os.path.isfile(real):
                continue
        except ValueError:
            continue
        rel = os.path.relpath(real, root).replace(os.sep, "/")
        with open(real, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
        numbers = _current_lines(entry, lines)
        if not numbers and not entry.get("deletion"):
            continue
        chunks.extend([f"diff --git a/{rel} b/{rel}", f"--- a/{rel}", f"+++ b/{rel}"])
        for first, last in _ranges(numbers):
            count = last - first + 1
            chunks.append(f"@@ -0,0 +{first},{count} @@")
            chunks.extend("+" + lines[number - 1] for number in range(first, last + 1))
        if entry.get("deletion"):
            chunks.extend(["@@ -1,1 +0,0 @@", "-mainframe-session-deletion"])
    return "\n".join(chunks) + ("\n" if chunks else "")


def whole_files(session_id, cwd, include_subagents=True):
    """Absolute paths wholly owned by a successful Write in this scope."""
    root = os.path.realpath(cwd)
    result = set()
    for file_path, entry in _merge_states(
        _state_paths(session_id, include_subagents)
    ).items():
        real = os.path.realpath(file_path)
        try:
            if (entry.get("whole") and os.path.isfile(real)
                    and os.path.commonpath((root, real)) == root):
                result.add(real)
        except ValueError:
            continue
    return result


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
