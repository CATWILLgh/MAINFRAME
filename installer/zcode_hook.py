"""Thin ZCode hook transport installed beside unchanged canonical detectors.

Native event normalization and private session state live here; canonical
detector semantics remain unchanged.
Operational failure is neutral: only a positive canonical finding produces
native output.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sqlite3
import stat
import subprocess
import sys
import time
from typing import BinaryIO


ROOT = Path(__file__).resolve().parent
PRE_SHELL_HOOKS = ("mainframe-secret-access", "mainframe-rg-short-replace", "mainframe-destructive-operations", "mainframe-commit-secrets")
PRE_SHELL_TRANSPORT = "mainframe-pre-shell"
SUPPORTED_HOOKS = frozenset({*PRE_SHELL_HOOKS, PRE_SHELL_TRANSPORT, "mainframe-code-quality"})
MAX_INPUT_BYTES = 262_144
MAX_MESSAGE_CHARS = 6_000
MAX_OUTPUT_BYTES = 32_768
MAX_ROOTS = 4_096
COMMIT_BUDGET_SECONDS = 3.0
MAX_EVENTS = 4_096
EVENT_TTL = 7 * 24 * 60 * 60
MAX_ID_CHARS = 512
_MISSING = object()


def _native_value(data: dict, snake: str, camel: str):
    """Return one documented alias, rejecting conflicting duplicate fields."""
    first = data.get(snake, _MISSING)
    second = data.get(camel, _MISSING)
    if first is not _MISSING and second is not _MISSING and first != second:
        return _MISSING
    return second if first is _MISSING else first


def _event_identity(data: dict) -> tuple[str, str] | None:
    scope = _native_value(data, "session_id", "sessionId")
    operations = [data[key] for key in ("tool_use_id", "toolUseId", "toolCallId") if key in data]
    if not operations or any(value != operations[0] for value in operations):
        return None
    operation = operations[0]
    values = (scope, operation)
    if not all(
        isinstance(value, str) and 0 < len(value) <= MAX_ID_CHARS
        for value in values
    ):
        return None
    return scope, operation


def _private_database(state: Path) -> Path | None:
    """Validate private ownership before opening bounded correctness state."""
    if state.is_symlink():
        return None
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = state.stat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_mode & 0o077
    ):
        return None

    database = state / "events.sqlite3"
    if database.is_symlink():
        return None
    flags = os.O_CREAT | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    descriptor = os.open(database, flags, 0o600)
    try:
        database_metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(database_metadata.st_mode)
            or database_metadata.st_uid != os.getuid()
            or database_metadata.st_mode & 0o077
        ):
            return None
    finally:
        os.close(descriptor)

    return database


def claim_event(data: dict, state: Path, kind: str) -> bool:
    """Atomically claim one advisory delivery for a real native event."""
    identity = _event_identity(data)
    if identity is None or not isinstance(kind, str) or not kind:
        return False
    database = _private_database(state)
    if not database:
        return False
    scope, operation = identity
    key = hashlib.sha256(
        ("zcode\0" + kind + "\0" + scope + "\0" + operation).encode()
    ).hexdigest()
    with closing(sqlite3.connect(database, timeout=0.1)) as connection, connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, expires REAL)"
        )
        connection.execute("BEGIN IMMEDIATE")
        now = time.time()
        connection.execute("DELETE FROM events WHERE expires <= ?", (now,))
        if connection.execute(
            "SELECT 1 FROM events WHERE id = ?", (key,)
        ).fetchone():
            return False
        if connection.execute("SELECT count(*) FROM events").fetchone()[0] >= MAX_EVENTS:
            return False
        connection.execute("INSERT INTO events VALUES (?, ?)", (key, now + EVENT_TTL))
    return True


def _cwd(data: dict) -> str | None:
    value = data.get("cwd")
    if not isinstance(value, str) or not value or len(value) > 4096:
        return None
    path = Path(value)
    if not path.is_absolute() or not path.is_dir():
        return None
    return str(path.resolve())


def session_root(data: dict, state: Path, *, capture: bool = False) -> str | None:
    """Keep only a root delivered by a verified native session event."""
    scope = _native_value(data, "session_id", "sessionId")
    if not isinstance(scope, str) or not 0 < len(scope) <= MAX_ID_CHARS:
        return None
    root = _cwd(data) if capture else None
    if capture and (
        data.get("source") not in {"startup", "clear", "compact", "resume"}
        or root is None
    ):
        return None
    if not capture and not (state / "events.sqlite3").exists():
        return None
    database = _private_database(state)
    if not database:
        return None
    key = hashlib.sha256(("zcode\0session-root\0" + scope).encode()).hexdigest()
    with closing(sqlite3.connect(database, timeout=0.1)) as connection, connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS roots (id TEXT PRIMARY KEY, root TEXT, expires REAL)"
        )
        connection.execute("BEGIN IMMEDIATE")
        now = time.time()
        connection.execute("DELETE FROM roots WHERE expires <= ?", (now,))
        existing = connection.execute("SELECT root FROM roots WHERE id = ?", (key,)).fetchone()
        if capture:
            # A verified native lifecycle event may replace an earlier capture;
            # a shell event's mutable cwd never may.
            if existing:
                connection.execute(
                    "UPDATE roots SET root = ?, expires = ? WHERE id = ?",
                    (root, now + EVENT_TTL, key),
                )
                return root
            if connection.execute("SELECT count(*) FROM roots").fetchone()[0] >= MAX_ROOTS:
                return None
            connection.execute("INSERT INTO roots VALUES (?, ?, ?)", (key, root, now + EVENT_TTL))
            return root
        if existing:
            connection.execute("UPDATE roots SET expires = ? WHERE id = ?", (now + EVENT_TTL, key))
            return existing[0]
        return None


def _load_detector(name: str):
    path = ROOT / "detectors" / (name + ".py")
    if not path.is_file() or path.is_symlink():
        return None
    module_name = "mainframe_zcode_detector_" + name.replace("-", "_")
    specification = importlib.util.spec_from_file_location(module_name, path)
    if specification is None or specification.loader is None:
        return None
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


@contextmanager
def _commit_budget(detector):
    """Reserve time for native output after the canonical Git inspection."""
    def expired(signum, frame):
        raise detector.InspectionUnavailable("native_time_budget")

    previous_handler = signal.getsignal(signal.SIGALRM)
    started = time.monotonic()
    signal.signal(signal.SIGALRM, expired)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, COMMIT_BUDGET_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0]:
            remaining = max(0.000001, previous_timer[0] - (time.monotonic() - started))
            signal.setitimer(signal.ITIMER_REAL, remaining, previous_timer[1])


def _native_output(event: str, field: str, message: str) -> dict:
    specific = {
        "hookEventName": event,
        field: message[:MAX_MESSAGE_CHARS],
    }
    if field == "permissionDecisionReason":
        specific["permissionDecision"] = "deny"
    output = {"hookSpecificOutput": specific}
    # ensure_ascii expands supplementary Unicode to twelve bytes per character.
    # Bound the complete serialized object (including print's newline), not text.
    while len(_serialize(output).encode("utf-8")) + 1 > MAX_OUTPUT_BYTES:
        specific[field] = specific[field][:len(specific[field]) // 2]
    return output


def _stop_block(message: str) -> dict:
    output = {"decision": "block", "reason": message[:MAX_MESSAGE_CHARS]}
    while len(_serialize(output).encode("utf-8")) + 1 > MAX_OUTPUT_BYTES:
        output["reason"] = output["reason"][:len(output["reason"]) // 2]
    return output


def _serialize(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _read_payload(stream: BinaryIO) -> dict | None:
    raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _project_root(cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return str(Path(result.stdout.strip()).resolve())
    except (OSError, RuntimeError, subprocess.SubprocessError):
        pass
    return cwd


def _edit_paths(data: dict, cwd: str) -> list[str]:
    tool_input = _native_value(data, "tool_input", "toolInput")
    if not isinstance(tool_input, dict):
        return []
    values = [tool_input[key] for key in ("file_path", "filePath", "path") if key in tool_input]
    if not values or any(value != values[0] for value in values):
        return []
    value = values[0]
    if not isinstance(value, str) or not value:
        return []
    path = Path(value)
    return [str(path if path.is_absolute() else Path(cwd) / path)]


def _quality_dispatch(data: dict, state: Path, event: str) -> dict | None:
    cwd = _cwd(data)
    scope = _native_value(data, "session_id", "sessionId")
    tool = _native_value(data, "tool_name", "toolName")
    if cwd is None or not isinstance(scope, str) or not 0 < len(scope) <= MAX_ID_CHARS:
        return None
    detector = _load_detector("mainframe-code-quality")
    if detector is None:
        return None
    workspace = _project_root(cwd)

    if event == "PreToolUse":
        identity = _event_identity(data)
        paths = _edit_paths(data, cwd)
        if tool not in {"Write", "Edit"} or identity is None or not paths:
            return None
        result = detector.capture_before(
            scope,
            workspace,
            identity[1],
            paths,
            state_namespace="mainframe-zcode-v2",
            state_root=state,
        )
        if result.advisory and claim_event(data, state, "mainframe-code-quality:pre"):
            return _native_output(event, "additionalContext", result.advisory)
        return None

    if event in {"PostToolUse", "PostToolUseFailure"}:
        identity = _event_identity(data)
        if tool not in {"Write", "Edit"} or identity is None:
            return None
        result = detector.record_after(
            scope,
            workspace,
            identity[1],
            succeeded=event == "PostToolUse",
            state_namespace="mainframe-zcode-v2",
            state_root=state,
        )
        if result.advisory and claim_event(data, state, "mainframe-code-quality:post"):
            return _native_output(event, "additionalContext", result.advisory)
        return None

    if event == "Stop":
        result = detector.check_completion(
            scope, workspace, state_namespace="mainframe-zcode-v2", state_root=state
        )
        if result.block_reason:
            return _stop_block(result.block_reason)
        # Stop advice is not visible to the responsible model unless it forces
        # another turn. Keep advisory-only results silent at this event.
    return None


def _combine_pre_shell(outputs: list[dict], event: str) -> dict | None:
    reasons = []
    advice = []
    for output in outputs:
        specific = output.get("hookSpecificOutput", {})
        reason = specific.get("permissionDecisionReason")
        context = specific.get("additionalContext")
        if isinstance(reason, str) and reason and reason not in reasons:
            reasons.append(reason)
        if isinstance(context, str) and context and context not in advice:
            advice.append(context)
    if not reasons and not advice:
        return None
    specific = {"hookEventName": event}
    if reasons:
        specific.update(permissionDecision="deny", permissionDecisionReason="\n\n".join(reasons))
    if advice:
        specific["additionalContext"] = "\n\n".join(advice)
    output = {"hookSpecificOutput": specific}
    for field in ("permissionDecisionReason", "additionalContext"):
        if field in specific:
            specific[field] = specific[field][:MAX_MESSAGE_CHARS]
    while len(_serialize(output).encode("utf-8")) + 1 > MAX_OUTPUT_BYTES:
        field = max(
            (name for name in ("permissionDecisionReason", "additionalContext") if name in specific),
            key=lambda name: len(specific[name]),
        )
        specific[field] = specific[field][:len(specific[field]) // 2]
    return output


def _dispatch_data(name: str, state: Path, data: dict) -> dict | None:
    if name not in SUPPORTED_HOOKS or (ROOT / (".disabled-" + name)).exists():
        return None
    event = _native_value(data, "hook_event_name", "hookEventName")
    if name == PRE_SHELL_TRANSPORT:
        outputs = [
            output for hook in PRE_SHELL_HOOKS
            if (output := _dispatch_data(hook, state, data)) is not None
        ]
        return _combine_pre_shell(outputs, event) if isinstance(event, str) else None
    if name == "mainframe-destructive-operations" and event == "SessionStart":
        session_root(data, state, capture=True)
        return None
    if name == "mainframe-code-quality":
        return _quality_dispatch(data, state, event)
    if event != "PreToolUse":
        return None
    if _native_value(data, "tool_name", "toolName") != "Bash":
        return None
    tool_input = _native_value(data, "tool_input", "toolInput")
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if not isinstance(command, str):
        return None

    detector = _load_detector(name)
    if detector is None:
        return None
    if name == "mainframe-secret-access":
        reason = detector.decision_reason(command)
        if isinstance(reason, str) and reason:
            return _native_output(event, "permissionDecisionReason", reason)
        return None

    if name in {"mainframe-commit-secrets", "mainframe-destructive-operations"}:
        cwd = _cwd(data)
        if cwd is None:
            return None
        if name == "mainframe-destructive-operations":
            root = session_root(data, state)
            if root is None:
                return None
            reason = detector.decision_reason(command, cwd, root)
            if isinstance(reason, str) and reason:
                return _native_output(event, "permissionDecisionReason", reason)
            return None
        with _commit_budget(detector):
            result = detector.check_command(command, cwd)
        if isinstance(result.block_reason, str) and result.block_reason:
            return _native_output(event, "permissionDecisionReason", result.block_reason)
        message = result.advisory
    else:
        message = detector.advisory_message(command)
    if not isinstance(message, str) or not message:
        return None
    if not claim_event(data, state, name):
        return None
    return _native_output(event, "additionalContext", message)


def dispatch(name: str, state: Path, stream: BinaryIO) -> dict | None:
    """Return one native decision/context object, or the neutral result."""
    if name not in SUPPORTED_HOOKS or (ROOT / (".disabled-" + name)).exists():
        return None
    data = _read_payload(stream)
    if data is None:
        return None
    return _dispatch_data(name, state, data)


def main() -> None:
    if len(sys.argv) != 3 or not sys.argv[2]:
        return
    try:
        payload = dispatch(sys.argv[1], Path(sys.argv[2]), sys.stdin.buffer)
        if payload is not None:
            # Bound message fields before serialization. Never truncate JSON.
            print(_serialize(payload))
    except Exception:
        # Failure is neutral, never a denial or evidence that the action is clean.
        return


if __name__ == "__main__":
    main()
