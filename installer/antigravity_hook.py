#!/usr/bin/env python3
"""Event-preserving Antigravity hook transport.

Antigravity cannot neutrally defer a clean PreToolUse decision. This bridge
therefore analyzes completed native tool calls at PostInvocation, injects only
positive contextual findings, and uses Stop only for findings attributed to an
exact edit payload and still present in the file.
"""

from __future__ import annotations

from collections import Counter
from contextlib import closing
from datetime import datetime
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

try:
    from .antigravity_hook_state import EVENT_TTL, claim_event, open_state
except ImportError:
    from antigravity_hook_state import EVENT_TTL, claim_event, open_state


ROOT = Path(__file__).resolve().parent
MAX_INPUT_BYTES = 262_144
MAX_TRANSCRIPT_BYTES = 8 * 1024 * 1024
MAX_MESSAGE_CHARS = 6_000
EDIT_TOOLS = {"replace_file_content", "write_to_file"}


def _read_payload() -> dict | None:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return None
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _load_detector(name: str):
    path = ROOT / "detectors" / (name + ".py")
    if not path.is_file() or path.is_symlink():
        return None
    specification = importlib.util.spec_from_file_location(
        "mainframe_antigravity_" + name.replace("-", "_"), path
    )
    if specification is None or specification.loader is None:
        return None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _workspace(data: dict) -> Path | None:
    values = data.get("workspacePaths")
    if not isinstance(values, list):
        return None
    for value in values:
        if isinstance(value, str):
            path = Path(value).expanduser().resolve()
            if path.is_dir():
                return path
    return None


def _latest_calls(data: dict) -> list[dict]:
    transcript = data.get("transcriptPath")
    if not isinstance(transcript, str):
        return []
    path = Path(transcript).expanduser()
    try:
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            return []
        resolved = path.resolve(strict=True)
        parts = set(resolved.parts)
        if "antigravity" not in parts or {"antigravity-cli", "antigravity-ide"} & parts:
            return []
        size = path.stat().st_size
        with path.open("rb") as stream:
            if size > MAX_TRANSCRIPT_BYTES:
                stream.seek(size - MAX_TRANSCRIPT_BYTES)
                stream.readline()
            lines = stream.read(MAX_TRANSCRIPT_BYTES).splitlines()
    except OSError:
        return []
    conversation = data.get("conversationId")
    if not isinstance(conversation, str) or not conversation:
        return []
    for raw in reversed(lines):
        try:
            row = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        calls = row.get("tool_calls") if isinstance(row, dict) else None
        if not isinstance(calls, list) or not calls:
            continue
        created = row.get("created_at", "")
        step = row.get("step_index", "")
        result = []
        for index, call in enumerate(calls):
            if not isinstance(call, dict) or not isinstance(call.get("name"), str):
                continue
            args = call.get("args")
            if not isinstance(args, dict):
                continue
            encoded = json.dumps(call, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            result.append({
                "id": f"{conversation}\0{created}\0{step}\0{index}\0{encoded}",
                "created": created,
                "name": call["name"].lower(),
                "args": args,
            })
        return result
    return []


def _inside(workspace: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        path = Path(value)
        path = (path if path.is_absolute() else workspace / path).resolve()
        path.relative_to(workspace)
        return path
    except (OSError, RuntimeError, ValueError):
        return None


def _command_context(call: dict, workspace: Path) -> tuple[str, str] | None:
    args = call["args"]
    command = args.get("CommandLine", args.get("command"))
    if not isinstance(command, str) or not command:
        return None
    raw_cwd = args.get("Cwd", args.get("cwd"))
    cwd = _inside(workspace, raw_cwd) if isinstance(raw_cwd, str) else workspace
    return (command, str(cwd or workspace))


def _created_epoch(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _shell_messages(call: dict, workspace: Path, state: Path) -> list[str]:
    if call["name"] != "run_command":
        return []
    context = _command_context(call, workspace)
    if context is None:
        return []
    command, cwd = context
    messages: list[str] = []
    for name in ("mainframe-secret-access", "mainframe-destructive-operations", "mainframe-rg-short-replace", "mainframe-commit-secrets"):
        if (ROOT / (".disabled-" + name)).exists():
            continue
        detector = _load_detector(name)
        if detector is None:
            continue
        message = None
        if name == "mainframe-secret-access":
            reason = detector.decision_reason(command)
            if reason:
                message = "Post-tool secret safety finding: " + reason
        elif name == "mainframe-destructive-operations":
            reason = detector.decision_reason(command, cwd, str(workspace))
            if reason:
                message = "Post-tool destructive-action finding: " + reason
        elif name == "mainframe-rg-short-replace":
            message = detector.advisory_message(command)
        else:
            result = detector.check_recorded_command(
                command, cwd, started_at=_created_epoch(call.get("created"))
            )
            message = result.advisory
        if isinstance(message, str) and message and claim_event(state, call["id"] + "\0" + name):
            messages.append(message)
    return messages


def _edit_payload(call: dict, workspace: Path) -> tuple[Path, str, str, int, bool] | None:
    if call["name"] not in EDIT_TOOLS:
        return None
    args = call["args"]
    path = _inside(workspace, args.get("TargetFile", args.get("path")))
    if path is None or not path.is_file() or path.is_symlink():
        return None
    if call["name"] == "replace_file_content":
        before, after = args.get("TargetContent"), args.get("ReplacementContent")
        if not isinstance(before, str) or not isinstance(after, str) or before == after:
            return None
        if args.get("AllowMultiple") is True or (after and after not in path.read_text(errors="replace")):
            return None
        line = args.get("StartLine")
        return path, before, after, line if isinstance(line, int) and line > 0 else 1, False
    content = args.get("CodeContent")
    if not isinstance(content, str) or args.get("Overwrite") is not False:
        return None
    if path.read_text(errors="replace") != content:
        return None
    return path, "", content, 1, True


def _store_findings(state: Path, scope: str, path: Path, rows: list, current: list) -> None:
    counts = Counter(row.fingerprint for row in current)
    deltas = Counter(row.fingerprint for row in rows)
    labels = {row.fingerprint: row.label for row in rows if row.blocking}
    connection = open_state(state)
    if connection is None:
        return
    with closing(connection), connection:
        for fingerprint, delta in deltas.items():
            if fingerprint not in labels:
                continue
            baseline = max(0, counts.get(fingerprint, 0) - delta)
            connection.execute(
                "INSERT INTO findings VALUES (?,?,?,?,?,?) ON CONFLICT(scope,path,fingerprint) "
                "DO UPDATE SET expires=excluded.expires",
                (scope, str(path), fingerprint, baseline, labels[fingerprint], time.time() + EVENT_TTL),
            )


def _fragment_diff(path: Path, workspace: Path, before: str, after: str, line: int) -> str:
    relative = path.relative_to(workspace).as_posix()
    text = "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile="a/" + relative, tofile="b/" + relative,
    ))
    if line <= 1:
        return text
    def shift(match):
        old = int(match.group(1)) + line - 1
        new = int(match.group(3)) + line - 1
        return f"@@ -{old}{match.group(2) or ''} +{new}{match.group(4) or ''} @@"
    return re.sub(r"@@ -(\d+)(,\d+)? \+(\d+)(,\d+)? @@", shift, text)


def _edit_messages(calls: list[dict], data: dict, workspace: Path, state: Path) -> list[str]:
    quality = None if (ROOT / ".disabled-mainframe-code-quality").exists() else _load_detector("mainframe-code-quality")
    fallow = None if (ROOT / ".disabled-mainframe-fallow-quality").exists() else _load_detector("mainframe-fallow-quality")
    checkpoint = None if (ROOT / ".disabled-mainframe-commit-checkpoint").exists() else _load_detector("mainframe-commit-checkpoint")
    conversation = data.get("conversationId")
    scope = hashlib.sha256(f"{conversation}\0{workspace}".encode()).hexdigest()
    messages: list[str] = []
    diffs, affected, wholly_owned = [], [], []
    for call in calls:
        edit = _edit_payload(call, workspace)
        if edit is None or not claim_event(state, call["id"] + "\0edit"):
            continue
        path, before, after, line, whole = edit
        if checkpoint is not None:
            message = checkpoint.observe(str(conversation), str(workspace), hashlib.sha256(call["id"].encode()).hexdigest(),
                                         checkpoint.text_lines(before, after), state_root=state)
            if message:
                messages.append(message)
        if quality is not None and path.suffix.lower() in quality.CODE_EXTENSIONS:
            before_rows = Counter(row.fingerprint for row in quality.scan_text(before, path.suffix))
            after_rows = quality.scan_text(after, path.suffix)
            introduced = []
            remaining = before_rows.copy()
            for row in after_rows:
                if remaining[row.fingerprint]:
                    remaining[row.fingerprint] -= 1
                else:
                    introduced.append(row)
            if introduced:
                current = quality.scan_text(path.read_text(errors="replace"), path.suffix)
                _store_findings(state, scope, path, introduced, current)
                listed = "; ".join(f"{path.relative_to(workspace)}:{line + row.line - 1} — {row.label}"
                                   for row in introduced[:6])
                messages.append("Code-quality finding introduced by the completed edit: " + listed)
        diff = _fragment_diff(path, workspace, before, after, line)
        if diff and path.suffix.lower() in getattr(fallow, "JS_EXTENSIONS", ()):
            diffs.append(diff)
            affected.append(str(path))
            if whole:
                wholly_owned.append(str(path))
    if fallow is not None and diffs:
        result = fallow.analyze(
            str(workspace), affected, "".join(diffs), wholly_owned_paths=wholly_owned, timeout_seconds=20
        )
        message = result.advisory or result.unavailable
        identity = (
            str(conversation) + "\0fallow-unavailable"
            if result.unavailable
            else str(conversation) + "\0fallow\0" + hashlib.sha256("".join(diffs).encode()).hexdigest()
        )
        if message and claim_event(state, identity):
            messages.append(message)
    return messages


def post_invocation(data: dict, state: Path) -> dict:
    workspace = _workspace(data)
    if workspace is None:
        return {}
    calls = _latest_calls(data)
    messages = [message for call in calls for message in _shell_messages(call, workspace, state)]
    messages.extend(_edit_messages(calls, data, workspace, state))
    if not messages:
        return {}
    message = "\n\n".join(messages)[:MAX_MESSAGE_CHARS]
    return {"injectSteps": [{"ephemeralMessage": message}]}


def stop(data: dict, state: Path) -> dict:
    workspace = _workspace(data)
    conversation = data.get("conversationId")
    execution = data.get("executionNum")
    if (workspace is None or not isinstance(conversation, str)
            or not isinstance(execution, int) or isinstance(execution, bool) or execution < 0
            or (ROOT / ".disabled-mainframe-code-quality").exists()):
        return {"decision": "stop"}
    detector = _load_detector("mainframe-code-quality")
    if detector is None:
        return {"decision": "stop"}
    connection = open_state(state)
    if connection is None:
        return {"decision": "stop"}
    scope = hashlib.sha256(f"{conversation}\0{workspace}".encode()).hexdigest()
    unresolved = []
    unresolved_identity = []
    with closing(connection), connection:
        rows = connection.execute(
            "SELECT path,fingerprint,baseline,label FROM findings WHERE scope=?", (scope,)
        ).fetchall()
        for raw_path, fingerprint, baseline, label in rows:
            path = _inside(workspace, raw_path)
            if path is None or not path.is_file() or path.suffix.lower() not in detector.CODE_EXTENSIONS:
                connection.execute("DELETE FROM findings WHERE scope=? AND path=? AND fingerprint=?",
                                   (scope, raw_path, fingerprint))
                continue
            counts = Counter(row.fingerprint for row in detector.scan_text(path.read_text(errors="replace"), path.suffix))
            if counts.get(fingerprint, 0) > baseline:
                unresolved.append(f"{path.relative_to(workspace)} — {label}")
                unresolved_identity.append(f"{raw_path}\0{fingerprint}\0{baseline}")
            else:
                connection.execute("DELETE FROM findings WHERE scope=? AND path=? AND fingerprint=?",
                                   (scope, raw_path, fingerprint))
    if not unresolved:
        return {"decision": "stop"}
    finding_set = hashlib.sha256("\0".join(sorted(unresolved_identity)).encode()).hexdigest()
    if not claim_event(state, f"{conversation}\0stop\0{execution}\0{finding_set}"):
        return {"decision": "stop"}
    reason = "Completion blocked by unresolved findings introduced in this execution:\n  - " + "\n  - ".join(unresolved[:6])
    return {"decision": "continue", "reason": reason[:MAX_MESSAGE_CHARS]}


def main() -> None:
    event = sys.argv[1] if len(sys.argv) == 3 else ""
    neutral = {"decision": "stop"} if event == "Stop" else {}
    try:
        data = _read_payload()
        if data is None:
            print(json.dumps(neutral))
        elif event == "PostInvocation":
            print(json.dumps(post_invocation(data, Path(sys.argv[2])), ensure_ascii=False))
        elif event == "Stop":
            print(json.dumps(stop(data, Path(sys.argv[2])), ensure_ascii=False))
        else:
            print(json.dumps(neutral))
    except Exception:
        print(json.dumps(neutral))


if __name__ == "__main__":
    main()
