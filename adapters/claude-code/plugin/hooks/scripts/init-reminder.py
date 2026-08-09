#!/usr/bin/env python3
"""Re-anchor the manually activated primary-session contract on long runs.

`/mainframe:init` is user-only. UserPromptExpansion records that direct manual
invocation for the current session; UserPromptSubmit then counts subsequent
primary-session prompts and injects a short reminder every N prompts (default
64) alongside the prompt that triggered it.

Claude Code reattaches invoked skills after compaction, so compact only resets
the counter. `/clear` and a fresh startup deactivate the reminder. Resume keeps
the prior state. Any payload carrying `agent_id` is rejected before state is
read or written: subagents neither advance the counter nor receive the note.

Fail-safe: any error -> exit 0 (no-op).
"""

import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_note, load_payload, log_event, run
except Exception:
    sys.exit(0)

INIT_COMMAND = "mainframe:init"
REMINDER_EVERY_N = 64
_STATE_DIR = os.path.join(tempfile.gettempdir(), "mainframe-init-reminder")

INIT_NOTE = (
    "MAINFRAME init remains active. Re-anchor on the already loaded primary-"
    "session contract: own the agreed outcome; keep product decisions, "
    "acceptance, orchestration, and final synthesis here; resolve technical "
    "and architectural uncertainty independently through evidence; return to "
    "the user only for a product choice, sensitive external authority, a "
    "conflict with the goal, or objectively missing input. Communicate only a "
    "material result, risk, decision, or action in concise plain language. "
    "Preserve delivery boundaries: local recovery commits are allowed; push "
    "and branch or history changes require an explicit user request."
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
    directory = state_dir or _STATE_DIR
    key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
    return os.path.join(directory, key + ".json")


def _load(path):
    """Return `(active, turns)`; malformed or absent state is inactive."""
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        active = state.get("active") is True
        turns = int(state.get("turns", 0))
        return active, max(0, turns)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False, 0


def _save(path, active, turns):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"active": bool(active), "turns": max(0, int(turns))}, fh)
    except (OSError, TypeError, ValueError):
        pass


def _clear(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _is_init_expansion(payload):
    return (
        payload.get("expansion_type") == "slash_command"
        and payload.get("command_name") == INIT_COMMAND
        and payload.get("command_source") == "plugin"
    )


def should_remind(active, turns, every):
    return active and turns > 0 and every > 0 and turns % every == 0


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
            _save(path, True, 0)
            log_event("init_reminder_activated", {}, payload)
        return

    if event == "SessionStart":
        source = payload.get("source")
        if source in ("startup", "clear"):
            _clear(path)
        elif source == "compact":
            active, _ = _load(path)
            if active:
                _save(path, True, 0)
        return

    if event != "UserPromptSubmit":
        return

    active, turns = _load(path)
    if not active:
        return

    turns += 1
    reminded = should_remind(active, turns, _every())
    _save(path, True, turns)
    if reminded:
        emit_note("UserPromptSubmit", INIT_NOTE)
    log_event(
        "init_reminder",
        {"turn": turns, "reminded": reminded, "every": _every()},
        payload,
    )


if __name__ == "__main__":
    run(main)
