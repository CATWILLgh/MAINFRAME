#!/usr/bin/env python3
"""Thin MiniMax Plugin V1 transport for unchanged MAINFRAME detectors."""

from __future__ import annotations

from collections import Counter
from contextlib import closing, contextmanager
import difflib
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


try:
    from . import native_skill_reminder as skill_advice
except ImportError:
    try:
        import native_skill_reminder as skill_advice
    except ImportError:
        skill_advice = None


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DETECTORS = PLUGIN_ROOT / "hooks/detectors"
HOOKS = PLUGIN_ROOT / "hooks"
HOOK_NAMES = frozenset({
    "mainframe-secret-access", "mainframe-rg-short-replace",
    "mainframe-destructive-operations", "mainframe-commit-secrets",
    "mainframe-code-quality", "mainframe-fallow-quality", "mainframe-commit-checkpoint", "mainframe-skill-reminder",
})
MAX_INPUT_BYTES = 1_048_576
MAX_MESSAGE_CHARS = 6_000
MAX_CONTEXT_CHARS = 60_000
MAX_OUTPUT_BYTES = 65_536
MAX_SNAPSHOT_BYTES = 2_000_000
MAX_ID_CHARS = 512
MAX_EVENTS = 4_096
EVENT_TTL = 7 * 24 * 60 * 60
COMMIT_BUDGET_SECONDS = 3.0
FALLOW_BUDGET_SECONDS = 7


def _value(data: dict, snake: str, camel: str):
    a, b = data.get(snake), data.get(camel)
    if snake in data and camel in data and a != b:
        return None
    return a if snake in data else b


def _read_payload(stream: BinaryIO) -> dict | None:
    raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return None
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _state_root(plugin_data: Path) -> Path | None:
    try:
        if not plugin_data.is_absolute() or plugin_data.is_symlink():
            return None
        root = plugin_data / "mainframe"
        if root.is_symlink():
            return None
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        meta = root.stat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o077:
            return None
        return root
    except OSError:
        return None


def _database(state: Path) -> Path | None:
    path = state / "events.sqlite3"
    try:
        if path.is_symlink():
            return None
        flags = os.O_CREAT | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"): flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            meta = os.fstat(descriptor)
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o077:
                return None
        finally:
            os.close(descriptor)
        return path
    except OSError:
        return None


def _connection(state: Path):
    path = _database(state)
    if path is None:
        return None
    con = sqlite3.connect(path, timeout=0.1)
    con.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, expires REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, path TEXT, before BLOB, existed INTEGER, expires REAL)")
    return con


def claim_event(state: Path, identity: str) -> bool:
    if not isinstance(identity, str) or not identity:
        return False
    con = _connection(state)
    if con is None:
        return False
    key = hashlib.sha256(("minimax\0" + identity).encode()).hexdigest()
    with closing(con), con:
        con.execute("BEGIN IMMEDIATE")
        now = time.time()
        con.execute("DELETE FROM events WHERE expires <= ?", (now,))
        con.execute("DELETE FROM snapshots WHERE expires <= ?", (now,))
        if con.execute("SELECT 1 FROM events WHERE id=?", (key,)).fetchone(): return False
        if con.execute("SELECT count(*) FROM events").fetchone()[0] >= MAX_EVENTS: return False
        con.execute("INSERT INTO events VALUES (?,?)", (key, now + EVENT_TTL))
    return True


def _load_detector(name: str):
    path = DETECTORS / (name + ".py")
    if name not in HOOK_NAMES or (HOOKS / (".disabled-" + name)).exists() or not path.is_file() or path.is_symlink():
        return None
    spec = importlib.util.spec_from_file_location("mainframe_minimax_" + name.replace("-", "_"), path)
    if spec is None or spec.loader is None: return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _cwd(data: dict) -> Path | None:
    value = data.get("cwd")
    if not isinstance(value, str) or not value or len(value) > 4096: return None
    try:
        path = Path(value).resolve(strict=True)
        return path if path.is_dir() else None
    except (OSError, RuntimeError):
        return None


def _project_root(cwd: Path) -> Path:
    try:
        result = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True, timeout=2, check=False)
        if result.returncode == 0 and result.stdout.strip():
            root = Path(result.stdout.strip()).resolve(strict=True)
            if root.is_dir(): return root
    except (OSError, RuntimeError, subprocess.SubprocessError):
        pass
    return cwd


def _identity(data: dict) -> tuple[str, str] | None:
    session = _value(data, "session_id", "sessionId")
    operation = _value(data, "tool_use_id", "toolUseId")
    if operation is None: operation = data.get("toolCallId")
    if not all(isinstance(v, str) and 0 < len(v) <= MAX_ID_CHARS for v in (session, operation)):
        return None
    return session, operation


def _tool(data: dict) -> tuple[str, dict] | None:
    name = _value(data, "tool_name", "toolName")
    inputs = _value(data, "tool_input", "toolInput")
    if not isinstance(name, str) or not isinstance(inputs, dict): return None
    return name, inputs


def _path(data: dict, cwd: Path) -> Path | None:
    tool = _tool(data)
    if tool is None: return None
    _, inputs = tool
    values = [inputs[k] for k in ("file_path", "filePath", "path") if k in inputs]
    if not values or any(value != values[0] for value in values): return None
    value = values[0]
    if not isinstance(value, str) or not value: return None
    try:
        path = Path(value)
        path = (path if path.is_absolute() else cwd / path).resolve(strict=False)
        path.relative_to(_project_root(cwd))
        return path
    except (OSError, RuntimeError, ValueError):
        return None


def _serialize(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _output(event: str, *, context: str | None = None, deny: str | None = None) -> dict | None:
    if not context and not deny: return None
    specific = {"hookEventName": event}
    if context:
        limit = MAX_CONTEXT_CHARS if event in {"SessionStart", "SubagentStart"} else MAX_MESSAGE_CHARS
        specific["additionalContext"] = context[:limit]
    if deny:
        specific["permissionDecision"] = "deny"
        specific["permissionDecisionReason"] = deny[:MAX_MESSAGE_CHARS]
    output = {"hookSpecificOutput": specific}
    while len(_serialize(output).encode()) + 1 > MAX_OUTPUT_BYTES:
        key = "additionalContext" if len(specific.get("additionalContext", "")) >= len(specific.get("permissionDecisionReason", "")) else "permissionDecisionReason"
        specific[key] = specific[key][:max(1, len(specific[key]) // 2)]
    return output


@contextmanager
def _commit_budget(detector):
    if not hasattr(signal, "SIGALRM"):
        yield
        return
    def expired(signum, frame): raise detector.InspectionUnavailable("native_time_budget")
    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, expired)
    started = time.monotonic()
    old_timer = signal.setitimer(signal.ITIMER_REAL, COMMIT_BUDGET_SECONDS)
    try: yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, max(0.000001, old_timer[0] - (time.monotonic() - started)), old_timer[1])


def _save_snapshot(data: dict, cwd: Path, state: Path) -> None:
    identity, path = _identity(data), _path(data, cwd)
    if identity is None or path is None or path.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte"}: return
    existed = path.is_file() and not path.is_symlink()
    try: before = path.read_bytes() if existed else b""
    except OSError: return
    if len(before) > MAX_SNAPSHOT_BYTES: return
    con = _connection(state)
    if con is None: return
    key = hashlib.sha256((identity[0] + "\0" + identity[1]).encode()).hexdigest()
    with closing(con), con:
        con.execute("DELETE FROM snapshots WHERE expires <= ?", (time.time(),))
        con.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?)",
                    (key, str(path), before, int(existed), time.time() + 3600))


def _take_snapshot(data: dict, state: Path) -> tuple[Path, bytes, bool] | None:
    identity = _identity(data)
    if identity is None: return None
    con = _connection(state)
    if con is None: return None
    key = hashlib.sha256((identity[0] + "\0" + identity[1]).encode()).hexdigest()
    with closing(con), con:
        row = con.execute("SELECT path,before,existed FROM snapshots WHERE id=?", (key,)).fetchone()
        con.execute("DELETE FROM snapshots WHERE id=?", (key,))
    if not row: return None
    path = Path(row[0])
    try:
        if path.is_symlink() or not path.is_file(): return None
        after = path.read_bytes()
    except OSError: return None
    if len(after) > MAX_SNAPSHOT_BYTES: return None
    return path, bytes(row[1]), bool(row[2])


def _quality_pre(data: dict, cwd: Path, state: Path) -> str | None:
    identity, path = _identity(data), _path(data, cwd)
    detector = _load_detector("mainframe-code-quality")
    if detector is None or identity is None or path is None: return None
    result = detector.capture_before(identity[0], str(_project_root(cwd)), identity[1], [str(path)],
                                     state_namespace="mainframe-minimax-v1", state_root=state)
    return result.advisory


def _quality_post(data: dict, cwd: Path, state: Path) -> str | None:
    identity = _identity(data)
    detector = _load_detector("mainframe-code-quality")
    if detector is None or identity is None: return None
    response = _value(data, "tool_response", "toolResponse")
    failed = isinstance(response, dict) and any(response.get(k) is True for k in ("isError", "is_error", "error"))
    result = detector.record_after(identity[0], str(_project_root(cwd)), identity[1], succeeded=not failed,
                                   state_namespace="mainframe-minimax-v1", state_root=state)
    return result.advisory


def _fallow_post(data: dict, cwd: Path, state: Path) -> str | None:
    detector = _load_detector("mainframe-fallow-quality")
    snapshot = _take_snapshot(data, state)
    if detector is None or snapshot is None: return None
    path, before, existed = snapshot
    try:
        root = _project_root(cwd)
        path.relative_to(root)
        after = path.read_bytes()
        before_text, after_text = before.decode("utf-8", "replace"), after.decode("utf-8", "replace")
    except (OSError, RuntimeError, ValueError): return None
    if before_text == after_text: return None
    relative = path.relative_to(root).as_posix()
    diff = "".join(difflib.unified_diff(before_text.splitlines(keepends=True), after_text.splitlines(keepends=True),
                                        fromfile="a/" + relative, tofile="b/" + relative))
    result = detector.analyze(str(root), [str(path)], diff,
                              wholly_owned_paths=[] if existed else [str(path)],
                              timeout_seconds=FALLOW_BUDGET_SECONDS)
    message = result.advisory or result.unavailable
    identity = _identity(data)
    if not message or identity is None: return None
    kind = "unavailable" if result.unavailable else hashlib.sha256(diff.encode()).hexdigest()
    return message if claim_event(state, identity[0] + "\0fallow\0" + kind) else None


def session_start(data: dict) -> dict | None:
    event = _value(data, "hook_event_name", "hookEventName")
    if event not in {"SessionStart", "SubagentStart"}: return None
    try: text = (PLUGIN_ROOT / "instructions/global.md").read_text()
    except OSError: return None
    return _output(event, context="MAINFRAME global operating instructions:\n\n" + text)


def pre_tool(data: dict, state: Path) -> dict | None:
    cwd, tool = _cwd(data), _tool(data)
    if cwd is None or tool is None: return None
    name, inputs = tool
    contexts, denials = [], []
    if name in {"write", "edit"}:
        if not (HOOKS / ".disabled-mainframe-fallow-quality").exists():
            _save_snapshot(data, cwd, state)
        note = _quality_pre(data, cwd, state)
        if note: contexts.append(note)
    elif name == "bash":
        command = inputs.get("command")
        if not isinstance(command, str): return None
        for detector_name in ("mainframe-secret-access", "mainframe-destructive-operations"):
            detector = _load_detector(detector_name)
            if detector is None: continue
            reason = (detector.decision_reason(command) if detector_name == "mainframe-secret-access"
                      else detector.decision_reason(command, str(cwd), str(_project_root(cwd))))
            if reason: denials.append(reason)
        detector = _load_detector("mainframe-commit-secrets")
        if detector is not None:
            with _commit_budget(detector): result = detector.check_command(command, str(cwd))
            if result.block_reason: denials.append(result.block_reason)
            elif result.advisory: contexts.append(result.advisory)
        detector = _load_detector("mainframe-rg-short-replace")
        if detector is not None:
            note = detector.advisory_message(command)
            if note: contexts.append(note)
    return _output("PreToolUse", context="\n\n".join(dict.fromkeys(contexts)),
                   deny="\n\n".join(dict.fromkeys(denials)))


def _checkpoint_note(data: dict, cwd: Path, state: Path) -> str | None:
    identity, tool, path = _identity(data), _tool(data), _path(data, cwd)
    response = _value(data, "tool_response", "toolResponse")
    if isinstance(response, dict) and any(response.get(key) is True for key in ("isError", "is_error", "error")):
        return None
    detector = _load_detector("mainframe-commit-checkpoint")
    if identity is None or tool is None or path is None or detector is None:
        return None
    size = detector.text_lines(*(tool[1].get(key, "") for key in ("content", "old_string", "new_string")))
    return detector.observe(identity[0], str(cwd), identity[1], size, state_root=state)


def post_tool(data: dict, state: Path) -> dict | None:
    cwd, tool = _cwd(data), _tool(data)
    if cwd is None or tool is None or tool[0] not in {"write", "edit"}: return None
    notes = [n for n in (_quality_post(data, cwd, state), _fallow_post(data, cwd, state), _checkpoint_note(data, cwd, state)) if n]
    identity = _identity(data)
    if not notes or identity is None: return None
    message = "\n\n".join(dict.fromkeys(notes))
    if not claim_event(state, identity[0] + "\0quality-post\0" + identity[1] + hashlib.sha256(message.encode()).hexdigest()):
        return None
    return _output("PostToolUse", context=message)


def stop(data: dict, state: Path) -> dict | None:
    if data.get("stop_hook_active") is True: return None
    event = _value(data, "hook_event_name", "hookEventName")
    if event not in {"Stop", "SubagentStop"}: return None
    cwd = _cwd(data)
    session = _value(data, "session_id", "sessionId")
    detector = _load_detector("mainframe-code-quality")
    if cwd is None or detector is None or not isinstance(session, str): return None
    result = detector.check_completion(session, str(_project_root(cwd)),
                                       state_namespace="mainframe-minimax-v1", state_root=state)
    reason = result.block_reason
    if not isinstance(reason, str) or not reason: return None
    turn = data.get("turn_id")
    agent = data.get("agent_id") if event == "SubagentStop" else "root"
    if not isinstance(agent, str): agent = "unknown"
    identity = session + "\0" + event + "\0" + agent + "\0" + (turn if isinstance(turn, str) else hashlib.sha256((data.get("last_assistant_message") or "").encode()).hexdigest()) + "\0" + hashlib.sha256(reason.encode()).hexdigest()
    if not claim_event(state, identity): return None
    return {"decision": "block", "reason": reason[:MAX_MESSAGE_CHARS]}


def combine_reminder(result, note):
    if not note:
        return result
    if not result:
        return note
    specific = result.get("hookSpecificOutput", {})
    if specific.get("permissionDecision") == "deny":
        return result
    text = note.get("hookSpecificOutput", {}).get("additionalContext")
    if text:
        specific["additionalContext"] = "\n\n".join(filter(None, (specific.get("additionalContext"), text)))[:MAX_MESSAGE_CHARS]
    return result


def reminder_output(data, state):
    if skill_advice is None:
        return None
    if (HOOKS / ".disabled-mainframe-skill-reminder").exists():
        return None
    event = _value(data, "hook_event_name", "hookEventName")
    tool, identity, cwd = _tool(data), _identity(data), _cwd(data)
    if event not in {"PreToolUse", "PostToolUse"} or not tool or not identity or not cwd:
        return None
    name, inputs = tool
    if event == "PostToolUse" and skill_advice.known_failed(_value(data, "tool_response", "toolResponse")):
        return None
    command = inputs.get("command") if name == "bash" else (
        skill_advice.read_command(inputs, ("file_path", "path")) if name == "read" and event == "PostToolUse" else None)
    if not isinstance(command, str):
        return None
    message = skill_advice.advise(PLUGIN_ROOT / "scripts", PLUGIN_ROOT / "skills", state, cwd,
                                  *identity, command, event, agent=_value(data, "agent_id", "agentId"), detectors=HOOKS / "detectors")
    return _output(event, context=message) if message else None


def dispatch(data: dict, state: Path) -> dict | None:
    event = _value(data, "hook_event_name", "hookEventName")
    if event in {"SessionStart", "SubagentStart"}: return session_start(data)
    if event == "PreToolUse":
        result = pre_tool(data, state)
        if result and result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny":
            return result
        return combine_reminder(result, reminder_output(data, state))
    if event == "PostToolUse": return combine_reminder(post_tool(data, state), reminder_output(data, state))
    if event in {"Stop", "SubagentStop"}: return stop(data, state)
    return None


def main() -> None:
    if len(sys.argv) != 2: return
    try:
        runtime_bin = os.environ.get("MAINFRAME_RUNTIME_BIN")
        if runtime_bin and Path(runtime_bin).is_absolute():
            os.environ["PATH"] = runtime_bin + os.pathsep + os.environ.get("PATH", "")
        state = _state_root(Path(sys.argv[1]))
        data = _read_payload(sys.stdin.buffer)
        if state is None or data is None: return
        result = dispatch(data, state)
        if result is not None: print(_serialize(result))
    except Exception:
        return


if __name__ == "__main__": main()
