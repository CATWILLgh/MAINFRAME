"""Thin Codex hook transport installed beside canonical detectors."""

from __future__ import annotations

from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
from typing import BinaryIO


ROOT = Path(__file__).resolve().parent
PRE_SHELL_HOOKS = (
    "mainframe-secret-access",
    "mainframe-rg-short-replace",
    "mainframe-destructive-operations",
    "mainframe-commit-secrets",
)
PRE_SHELL_TRANSPORT = "mainframe-pre-shell"
SUPPORTED_HOOKS = frozenset({*PRE_SHELL_HOOKS, PRE_SHELL_TRANSPORT, "mainframe-code-quality"})
MAX_INPUT_BYTES = 262_144
MAX_MESSAGE_CHARS = 6_000
MAX_OUTPUT_BYTES = 32_768
MAX_EVENTS = 4_096
EVENT_TTL = 7 * 24 * 60 * 60
ADAPTER_NAMESPACE = "mainframe-codex-v2"
PATCH_PATH = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$")


def claim_event(data: dict, state: Path, kind: str = "advisory") -> bool:
    """Claim one advisory kind for one real native tool event."""
    scope, operation = data.get("session_id"), data.get("tool_use_id")
    if not all(
        isinstance(value, str) and 0 < len(value) <= 512
        for value in (scope, operation)
    ) or not isinstance(kind, str) or not kind:
        return False
    if state.is_symlink():
        return False
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    if state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
        return False
    database = state / "events.sqlite3"
    if database.is_symlink():
        return False
    fd = os.open(database, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    key = hashlib.sha256(
        (kind + "\0" + scope + "\0" + operation).encode()
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


def _read_payload(stream: BinaryIO) -> dict | None:
    raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return None
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _load_detector(name: str):
    path = ROOT / "detectors" / (name + ".py")
    if not path.is_file() or path.is_symlink():
        return None
    specification = importlib.util.spec_from_file_location(
        "mainframe_codex_detector_" + name.replace("-", "_"), path
    )
    if specification is None or specification.loader is None:
        return None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _context(event: str, message: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": message[:MAX_MESSAGE_CHARS],
        }
    }


def _deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason[:MAX_MESSAGE_CHARS],
        }
    }


def _command(data: dict) -> str | None:
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    value = tool_input.get("command")
    return value if isinstance(value, str) else None


def _patch(data: dict) -> str | None:
    tool_input = data.get("tool_input")
    if isinstance(tool_input, str):
        return tool_input
    if not isinstance(tool_input, dict):
        return None
    for key in ("patch", "input", "text", "command"):
        value = tool_input.get(key)
        if isinstance(value, str):
            return value
    return None


def _patch_paths(patch: str) -> list[str]:
    paths = []
    for line in patch.splitlines():
        match = PATCH_PATH.match(line)
        if match:
            paths.append(match.group(1))
    return list(dict.fromkeys(paths))


def _workspace(data: dict) -> str | None:
    value = data.get("cwd")
    if not isinstance(value, str) or not value:
        return None
    try:
        cwd = Path(value).resolve(strict=True)
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return str(Path(result.stdout.strip()).resolve(strict=True))
        return str(cwd)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return None


def _identity(data: dict, key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) and 0 < len(value) <= 512 else None


def _tool_succeeded(data: dict) -> bool:
    response = data.get("tool_response")
    return not (isinstance(response, dict) and response.get("isError") is True)


def _dispatch_quality(data: dict, state: Path, event: str) -> dict | None:
    workspace = _workspace(data)
    scope = _identity(data, "session_id")
    if workspace is None or scope is None:
        return None
    detector = _load_detector("mainframe-code-quality")
    if detector is None:
        return None

    if event == "PreToolUse":
        if data.get("tool_name") != "apply_patch":
            return None
        operation = _identity(data, "tool_use_id")
        patch = _patch(data)
        if operation is None or patch is None:
            return None
        paths = _patch_paths(patch)
        if not paths:
            return None
        result = detector.capture_before(
            scope, workspace, operation, paths,
            state_namespace=ADAPTER_NAMESPACE, state_root=state,
        )
        if result.advisory and claim_event(data, state, "mainframe-code-quality:pre"):
            return _context(event, result.advisory)
        return None

    if event == "PostToolUse":
        if data.get("tool_name") != "apply_patch":
            return None
        operation = _identity(data, "tool_use_id")
        if operation is None:
            return None
        result = detector.record_after(
            scope,
            workspace,
            operation,
            succeeded=_tool_succeeded(data),
            state_namespace=ADAPTER_NAMESPACE,
            state_root=state,
        )
        if result.advisory and claim_event(data, state, "mainframe-code-quality:post"):
            return _context(event, result.advisory)
        return None

    if event == "Stop":
        result = detector.check_completion(
            scope, workspace, state_namespace=ADAPTER_NAMESPACE, state_root=state
        )
        if result.block_reason and data.get("stop_hook_active") is not True:
            return {
                "decision": "block",
                "reason": result.block_reason[:MAX_MESSAGE_CHARS],
            }
        # Keep unresolved state, but never create a repeated automatic Stop loop.
        # Stop has no non-blocking model-context channel. Protection
        # availability advice is emitted on edit events when possible and is
        # deliberately silent here instead of forcing another model turn.
    return None


def _combine_pre_shell(outputs: list[dict], event: str) -> dict | None:
    reasons: list[str] = []
    advice: list[str] = []
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
    specific: dict[str, str] = {"hookEventName": event}
    if reasons:
        specific.update(
            permissionDecision="deny",
            permissionDecisionReason="\n\n".join(reasons)[:MAX_MESSAGE_CHARS],
        )
    if advice:
        specific["additionalContext"] = "\n\n".join(advice)[:MAX_MESSAGE_CHARS]
    output = {"hookSpecificOutput": specific}
    while len(json.dumps(output, ensure_ascii=True, separators=(",", ":")).encode()) + 1 > MAX_OUTPUT_BYTES:
        field = max(
            (key for key in ("permissionDecisionReason", "additionalContext") if key in specific),
            key=lambda key: len(specific[key]),
        )
        specific[field] = specific[field][: len(specific[field]) // 2]
    return output


def _dispatch_data(name: str, state: Path, data: dict) -> dict | None:
    if name not in SUPPORTED_HOOKS or (ROOT / (".disabled-" + name)).exists():
        return None
    event = data.get("hook_event_name")
    if name == PRE_SHELL_TRANSPORT:
        outputs = [
            output
            for hook in PRE_SHELL_HOOKS
            if (output := _dispatch_data(hook, state, data)) is not None
        ]
        return _combine_pre_shell(outputs, event) if isinstance(event, str) else None
    if name == "mainframe-code-quality":
        return _dispatch_quality(data, state, event)
    if event != "PreToolUse" or data.get("tool_name") != "Bash":
        return None
    command = _command(data)
    if command is None:
        return None
    detector = _load_detector(name)
    if detector is None:
        return None
    if name == "mainframe-secret-access":
        reason = detector.decision_reason(command)
        return _deny(reason) if isinstance(reason, str) and reason else None
    if name == "mainframe-destructive-operations":
        reason = detector.context_free_decision_reason(command)
        return _deny(reason) if isinstance(reason, str) and reason else None
    if name == "mainframe-commit-secrets":
        result = detector.check_context_free_metadata(command)
        return _deny(result.block_reason) if isinstance(result.block_reason, str) else None
    message = detector.advisory_message(command)
    if isinstance(message, str) and message and claim_event(data, state, name):
        return _context(event, message)
    return None


def dispatch(name: str, state: Path, stream: BinaryIO) -> dict | None:
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
        result = dispatch(sys.argv[1], Path(sys.argv[2]), sys.stdin.buffer)
        if result is not None:
            print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    except Exception:
        return


if __name__ == "__main__":
    main()
