"""Thin Codex hook transport installed beside canonical detectors."""

from __future__ import annotations

from contextlib import closing
import difflib
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
SUPPORTED_HOOKS = frozenset({*PRE_SHELL_HOOKS, PRE_SHELL_TRANSPORT, "mainframe-code-quality", "mainframe-commit-checkpoint", "mainframe-skill-reminder", "mainframe-subagent-selection", "mainframe-todo-limits", "mainframe-fallow-quality"})
# Exact verified V2 surface; V1 uses different fork controls.
SUBAGENT_TOOLS = {"collaborationspawn_agent"}
MAX_INPUT_BYTES = 262_144
MAX_MESSAGE_CHARS = 6_000
MAX_OUTPUT_BYTES = 32_768
MAX_EVENTS = 4_096
EVENT_TTL = 7 * 24 * 60 * 60
ADAPTER_NAMESPACE = "mainframe-codex-v2"
PATCH_PATH = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$")
PATCH_MOVE = re.compile(r"^\*\*\* Move to: (.+?)\s*$")
FALLOW_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte"}
FALLOW_MAX_BYTES = 2_000_000
FALLOW_MAX_PATHS = 64
FALLOW_ATTRIBUTION_UNAVAILABLE = "Fallow structural review was unavailable: the addressed TS/JS patch could not be reconstructed unambiguously. Review the changed structure; this advisory does not block the edit or completion."


def claim_event(data: dict, state: Path, kind: str = "advisory") -> bool:
    """Claim one advisory kind for one real native tool event."""
    scope, operation = _scope(data), data.get("tool_use_id")
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
        match = PATCH_PATH.match(line) or PATCH_MOVE.match(line)
        if match:
            paths.append(match.group(1))
    return list(dict.fromkeys(paths))


def _cwd(data: dict) -> Path | None:
    value = data.get("cwd")
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        return None
    try:
        cwd = Path(value).resolve(strict=True)
        return cwd if cwd.is_dir() else None
    except (OSError, RuntimeError):
        return None


def _edit_patch(data: dict, patch: str) -> str:
    cwd = _cwd(data)
    if cwd is None:
        return patch
    lines = []
    for line in patch.splitlines(keepends=True):
        match = PATCH_PATH.match(line) or PATCH_MOVE.match(line)
        if match and not Path(match[1]).is_absolute():
            line = line[:match.start(1)] + str(cwd / match[1]) + line[match.end(1):]
        lines.append(line)
    return "".join(lines)


def _workspace(data: dict) -> str | None:
    cwd = _cwd(data)
    if cwd is None:
        return None
    try:
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


def _scope(data: dict) -> str | None:
    session = _identity(data, "session_id")
    if data.get("agent_id") is not None and _identity(data, "agent_id") is None:
        return None
    agent = _identity(data, "agent_id")
    return "agent:" + hashlib.sha256((session + "\0" + agent).encode()).hexdigest() if session and agent else session


def _patch_blocks(patch: str):
    lines = patch.splitlines()
    if not lines or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise ValueError("unsupported patch frame")
    index = 1
    while index < len(lines) - 1:
        match = re.fullmatch(r"\*\*\* (Add|Update|Delete) File: (.+)", lines[index])
        if match is None:
            raise ValueError("unsupported patch header")
        index += 1
        body = []
        while index < len(lines) - 1 and PATCH_PATH.match(lines[index]) is None:
            body.append(lines[index])
            index += 1
        yield match[1], match[2], body


def _reverse_update(after: list[str], body: list[str]) -> list[str]:
    hunks = []
    for line in body:
        if line == "@@" or line.startswith("@@ "):
            hunks.append([])
        elif line == "*** End of File":
            continue
        elif hunks and line.startswith((" ", "+", "-")):
            hunks[-1].append(line)
        else:
            raise ValueError("unsupported update hunk")
    if not hunks:
        raise ValueError("missing update hunk")
    replacements = []
    previous_end = 0
    postimage = "\n" + "\n".join(after) + "\n"
    for hunk in hunks:
        old = [line[1:] for line in hunk if line[0] != "+"]
        new = [line[1:] for line in hunk if line[0] != "-"]
        if not new:
            raise ValueError("unanchored deletion")
        anchor = "\n" + "\n".join(new) + "\n"
        position = postimage.find(anchor)
        if position < 0 or postimage.find(anchor, position + 1) >= 0:
            raise ValueError("ambiguous or missing update")
        start = postimage.count("\n", 0, position)
        if start < previous_end:
            raise ValueError("ambiguous or overlapping update")
        previous_end = start + len(new)
        replacements.append((start, previous_end, old))
    before = list(after)
    for start, end, old in reversed(replacements):
        before[start:end] = old
    return before


def _fallow_diff(data: dict, workspace: str, patch: str):
    root, cwd = Path(workspace), Path(data["cwd"]).resolve(strict=True)
    diffs, affected, wholly_owned = [], [], []
    total = 0
    if any(PATCH_MOVE.match(line) for line in patch.splitlines()):
        raise ValueError("unsupported move attribution")
    for operation, raw, body in _patch_blocks(patch):
        if Path(raw).suffix.lower() not in FALLOW_SUFFIXES:
            continue
        path = Path(raw)
        path = path if path.is_absolute() else cwd / path
        path.relative_to(root)
        if ".." in path.parts or any(parent.is_symlink() for parent in (path, *path.parents) if parent.is_relative_to(root)):
            raise ValueError("unsafe path")
        if operation == "Delete" or not path.is_file():
            raise ValueError("missing addressed postimage")
        with path.open("rb") as stream:
            raw_after = stream.read(FALLOW_MAX_BYTES + 1)
        total += len(raw_after)
        if total > FALLOW_MAX_BYTES or len(affected) >= FALLOW_MAX_PATHS or str(path) in affected:
            raise ValueError("oversized or repeated edit scope")
        after = raw_after.decode("utf-8").splitlines()
        if operation == "Add":
            if any(not line.startswith("+") for line in body) or after != [line[1:] for line in body]:
                raise ValueError("created file changed before callback")
            before = []
            wholly_owned.append(str(path))
        else:
            before = _reverse_update(after, body)
        relative = path.relative_to(root).as_posix()
        diffs.extend(difflib.unified_diff([line + "\n" for line in before], [line + "\n" for line in after],
                                        fromfile="a/" + relative, tofile="b/" + relative))
        affected.append(str(path))
    diff = "".join(diffs)
    if len(diff.encode("utf-8")) > FALLOW_MAX_BYTES:
        raise ValueError("oversized diff")
    return affected, wholly_owned, diff


def _dispatch_fallow(data: dict, state: Path, event: str) -> dict | None:
    if event != "PostToolUse" or data.get("tool_name") != "apply_patch" or not _tool_succeeded(data):
        return None
    patch, workspace = _patch(data), _workspace(data)
    if not patch or not workspace or not _identity(data, "tool_use_id") or not _scope(data):
        return None
    if not any(Path(path).suffix.lower() in FALLOW_SUFFIXES for path in _patch_paths(patch)):
        return None
    detector = _load_detector("mainframe-fallow-quality")
    if detector is None:
        return None
    try:
        affected, owned, diff = _fallow_diff(data, workspace, patch)
        if not affected or not diff:
            return None
        result = detector.analyze(workspace, affected, diff, wholly_owned_paths=owned, timeout_seconds=7)
        message = result.advisory or result.unavailable
    except (OSError, ValueError, RuntimeError, UnicodeError):
        message = FALLOW_ATTRIBUTION_UNAVAILABLE
    if message and claim_event(data, state, "mainframe-fallow-quality:post"):
        return _context(event, message)
    return None


def _dispatch_quality(data: dict, state: Path, event: str) -> dict | None:
    if event == "SubagentStop" and _identity(data, "agent_id") is None:
        return None
    workspace = _workspace(data)
    scope = _scope(data)
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
        paths = _patch_paths(_edit_patch(data, patch))
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

    if event in {"Stop", "SubagentStop"}:
        result = detector.check_completion(
            scope, workspace, state_namespace=ADAPTER_NAMESPACE, state_root=state
        )
        if result.block_reason and data.get("stop_hook_active") is not True:
            return {
                "decision": "block",
                "reason": result.block_reason[:MAX_MESSAGE_CHARS],
            }
        if result.block_reason:
            reason = "MAINFRAME quality check remains unresolved after its repair continuation: " + result.block_reason
            return {"continue": False, "stopReason": reason[:MAX_MESSAGE_CHARS],
                    "systemMessage": reason[:MAX_MESSAGE_CHARS]}
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


def _dispatch_checkpoint(data: dict, state: Path, event: str) -> dict | None:
    if event != "PostToolUse" or data.get("tool_name") != "apply_patch" or not _tool_succeeded(data):
        return None
    scope, operation, workspace = _scope(data), _identity(data, "tool_use_id"), _workspace(data)
    patch = _patch(data)
    if not scope or not operation or not workspace or not patch or not _patch_paths(patch):
        return None
    try:
        root = Path(workspace)
        cwd = Path(data["cwd"])
        for raw in _patch_paths(patch):
            path = Path(raw)
            (path if path.is_absolute() else cwd / path).resolve().relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    detector = _load_detector("mainframe-commit-checkpoint")
    if detector is None:
        return None
    size = min(100_000, sum(line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
                            for line in patch.splitlines()))
    message = detector.observe(scope, workspace, operation, size, state_root=state)
    return _context(event, message) if message else None


def _dispatch_selection(data: dict) -> dict | None:
    if data.get("hook_event_name") != "PreToolUse" or data.get("tool_name") not in SUBAGENT_TOOLS:
        return None
    args = data.get("tool_input")
    if not isinstance(args, dict):
        return None
    detector = _load_detector("mainframe-subagent-selection")
    if detector is None:
        return None
    reason = detector.decision_reason(args.get("model"), args.get("reasoning_effort"))
    # V2 defaults to full history, which rejects model overrides natively.
    fork = args.get("fork_turns", "all")
    if reason or not isinstance(fork, str) or fork.strip().lower() != "none":
        return _deny((reason + " " if reason else "") +
                     'Use fork_turns="none" with a self-contained task brief; full-history inheritance cannot accept model overrides.')
    return None


def _dispatch_data(name: str, state: Path, data: dict) -> dict | None:
    if name not in SUPPORTED_HOOKS or (ROOT / (".disabled-" + name)).exists():
        return None
    event = data.get("hook_event_name")
    if name == "mainframe-subagent-selection":
        return _dispatch_selection(data)
    if name == "mainframe-fallow-quality":
        return _dispatch_fallow(data, state, event)
    if name == "mainframe-todo-limits":
        if event != "PreToolUse" or data.get("tool_name") != "apply_patch":
            return None
        patch = _patch(data)
        detector = _load_detector(name) if patch is not None else None
        if detector is None:
            return None
        reason = detector.check_patch(_workspace(data), _edit_patch(data, patch))
        return _deny(reason) if isinstance(reason, str) and reason else None
    if name == PRE_SHELL_TRANSPORT:
        outputs = [
            output
            for hook in PRE_SHELL_HOOKS
            if (output := _dispatch_data(hook, state, data)) is not None
        ]
        return _combine_pre_shell(outputs, event) if isinstance(event, str) else None
    if name == "mainframe-skill-reminder":
        if event != "SubagentStart" and (event not in {"PreToolUse", "PostToolUse"} or data.get("tool_name") != "Bash"):
            return None
        helper = ROOT / "skill_reminder.py"
        if not helper.is_file() or helper.is_symlink():
            return None
        spec = importlib.util.spec_from_file_location("mainframe_codex_skill_reminder", helper)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        detector = _load_detector(name)
        message = module.advisory(data, state, ROOT, detector) if detector else None
        return _context(event, message) if message else None
    if name == "mainframe-commit-checkpoint":
        return _dispatch_checkpoint(data, state, event)
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
