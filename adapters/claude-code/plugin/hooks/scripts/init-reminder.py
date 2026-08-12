#!/usr/bin/env python3
"""Re-anchor the manually activated primary-session contract on long runs.

`/mainframe:init` is user-only. UserPromptExpansion records that direct manual
invocation for the current session; UserPromptSubmit then counts subsequent
primary-session prompts and injects a short reminder every N prompts (default
64) alongside the prompt that triggered it.

Compaction re-injects invoked skills only within a shared context budget, so an
active session receives the same short reminder immediately after compact and
its counter resets. `/clear` and a fresh startup deactivate the reminder.
Resume keeps the prior state. Any payload carrying `agent_id` is rejected before
state is read or written: subagents neither advance the counter nor receive the
note.

Fail-safe: any error -> exit 0 (no-op).
"""

import hashlib
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_note, load_payload, log_event, run
except Exception:
    sys.exit(0)

INIT_COMMAND = "mainframe:init"
REMINDER_EVERY_N = 64
_STATE_DIR = os.path.join(tempfile.gettempdir(), "mainframe-init-reminder")
_LOCK_STALE_SECONDS = 60
_STATE_STALE_SECONDS = 30 * 24 * 60 * 60

INIT_NOTE = (
    "MAINFRAME init remains active. Re-anchor on the already loaded primary-"
    "session contract: own the agreed outcome; keep product decisions, "
    "acceptance, orchestration, and final synthesis here; resolve technical "
    "and architectural uncertainty independently through evidence; return to "
    "the user only for a product or business-logic choice, a material "
    "infrastructure choice, missing authority for a destructive, irreversible, "
    "or externally mutating action, a conflict with the goal, or objectively "
    "missing input. DoD and /goal grant no action authority beyond what the "
    "user explicitly stated. Communicate only a "
    "material result, risk, decision, or action in concise plain language. "
    "Preserve delivery boundaries: ordinary new local recovery commits on the "
    "session-start branch are allowed; push, branch changes, and every other "
    "history operation require an explicit user request."
)


def _every():
    """Configured interval, falling back to the agreed 64 main turns."""
    raw = os.environ.get("MAINFRAME_INIT_REMINDER_EVERY")
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return REMINDER_EVERY_N


def _state_path(session_id, state_dir=None):
    directory = state_dir or os.environ.get(
        "MAINFRAME_INIT_REMINDER_STATE_DIR", _STATE_DIR)
    key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
    return os.path.join(directory, key + ".json")


def _load(path):
    """Return `(active, turns)`; only absent state is inactive."""
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        active = state.get("active") is True
        turns = int(state.get("turns", 0))
        return active, max(0, turns)
    except FileNotFoundError:
        return False, 0


def _save(path, active, turns):
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".state-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"active": bool(active), "turns": max(0, int(turns))}, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def _clear(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@contextmanager
def _session_lock(path):
    lock = path + ".lock"
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    for _ in range(100):
        try:
            os.mkdir(lock, mode=0o700)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock) > _LOCK_STALE_SECONDS:
                    os.rmdir(lock)
                    continue
            except FileNotFoundError:
                continue
            time.sleep(0.01)
    else:
        raise TimeoutError("init reminder state lock unavailable")
    try:
        yield
    finally:
        try:
            os.rmdir(lock)
        except FileNotFoundError:
            pass


def _cleanup_stale(directory):
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        return
    now = time.time()
    for name in names:
        path = os.path.join(directory, name)
        try:
            age = now - os.path.getmtime(path)
            if name.endswith(".lock") and age > _LOCK_STALE_SECONDS:
                os.rmdir(path)
            elif name.endswith(".json") and age > _STATE_STALE_SECONDS:
                os.unlink(path)
        except (FileNotFoundError, OSError):
            continue


def _is_init_expansion(payload):
    return (
        payload.get("expansion_type") == "slash_command"
        and payload.get("command_name") == INIT_COMMAND
        and payload.get("command_source") == "plugin"
    )


def should_remind(active, turns, every):
    return active and turns > 0 and every > 0 and turns % every == 0


def _log_telemetry(event, data, payload):
    if log_event(event, data, payload) == "error":
        raise RuntimeError("telemetry sink unavailable")


def main():
    payload = load_payload()

    # This contract belongs exclusively to the user-facing primary session.
    # Reject subagent payloads before even resolving their state path.
    if payload.get("agent_id"):
        return

    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return

    event = payload.get("hook_event_name") or ""
    path = _state_path(session_id)

    if event == "UserPromptExpansion":
        if _is_init_expansion(payload):
            with _session_lock(path):
                _save(path, True, 0)
            _log_telemetry("init_reminder_activated", {}, payload)
        return

    if event == "SessionStart":
        _cleanup_stale(os.path.dirname(path))
        source = payload.get("source")
        remind_after_compact = False
        with _session_lock(path):
            if source in ("startup", "clear"):
                _clear(path)
            elif source == "compact":
                active, _ = _load(path)
                if active:
                    _save(path, True, 0)
                    remind_after_compact = True
        if remind_after_compact:
            emit_note("SessionStart", INIT_NOTE)
        return

    if event != "UserPromptSubmit":
        return

    with _session_lock(path):
        active, turns = _load(path)
        if not active:
            return
        turns += 1
        reminded = should_remind(active, turns, _every())
        _save(path, True, turns)
    if reminded:
        emit_note("UserPromptSubmit", INIT_NOTE)
    _log_telemetry(
        "init_reminder",
        {"turn": turns, "reminded": reminded, "every": _every()},
        payload,
    )


if __name__ == "__main__":
    run(main)
