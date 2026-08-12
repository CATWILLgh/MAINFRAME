#!/usr/bin/env python3
"""Remind the primary session to maintain native auto-memory at context milestones.

Claude Code exposes the main transcript path to Stop hooks. Current local
transcripts include per-response input usage and explicit compact boundaries;
their format is not a documented public contract, so every parsing or state
failure is a silent no-op.

The reminder is advisory and main-session-only. It fires at most once when the
current compact segment first reaches each configured token milestone. State is
incremental and session-scoped so a large transcript is not reparsed on every
Stop and concurrent sessions do not share counters.
"""

import fcntl
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (
        emit_note, load_payload, log_hook_signal, run, stop_guard_cwd,
    )
except Exception:
    sys.exit(0)

TOKEN_MILESTONES = (300_000, 600_000, 900_000)
USAGE_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)

MEMORY_NOTE = (
    "Memory checkpoint (skip if nothing applies): preserve any durable fact a "
    "future session will need in native auto-memory now. Keep MEMORY.md as a "
    "concise index, move detail to topic files, update stale entries, and never "
    "store secrets, temporary progress, or guesses."
)


def _usage_tokens(row):
    message = row.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        values = [int(usage.get(field) or 0) for field in USAGE_FIELDS]
    except (TypeError, ValueError):
        return None
    total = sum(value for value in values if value >= 0)
    return total or None


def _initial_state(path, stat):
    return {
        "path": path,
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "offset": 0,
        "segment": "initial",
        "peak_tokens": 0,
        "notified_milestone": 0,
    }


def _load_state(handle, path, stat):
    try:
        handle.seek(0)
        state = json.load(handle)
    except Exception:
        return _initial_state(path, stat)
    if (
        state.get("path") != path
        or state.get("device") != stat.st_dev
        or state.get("inode") != stat.st_ino
        or not isinstance(state.get("offset"), int)
        or state["offset"] < 0
        or state["offset"] > stat.st_size
    ):
        return _initial_state(path, stat)
    return state


def _scan_appended(transcript, state):
    with open(transcript, "rb") as source:
        source.seek(state["offset"])
        while True:
            start = source.tell()
            raw = source.readline()
            if not raw:
                break
            if not raw.endswith(b"\n"):
                source.seek(start)
                break
            try:
                row = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            if row.get("type") == "system" and row.get("subtype") == "compact_boundary":
                state["segment"] = str(row.get("uuid") or f"offset-{start}")
                state["peak_tokens"] = 0
                state["notified_milestone"] = 0
            tokens = _usage_tokens(row)
            if tokens is not None:
                state["peak_tokens"] = max(int(state.get("peak_tokens") or 0), tokens)
        state["offset"] = source.tell()


def _reached_milestone(payload, state_dir=None):
    """Return (milestone, observed tokens) once per compact segment, else None."""
    session_id = payload.get("session_id")
    transcript = payload.get("transcript_path")
    if not isinstance(session_id, str) or not session_id or not transcript:
        return None
    transcript = os.path.realpath(os.path.expanduser(str(transcript)))
    try:
        stat = os.stat(transcript)
    except OSError:
        return None

    directory = state_dir or tempfile.gettempdir()
    key = hashlib.sha256(session_id.encode("utf-8", "replace")).hexdigest()[:16]
    state_path = os.path.join(directory, f"memory-reminder-{key}.json")
    try:
        os.makedirs(directory, exist_ok=True)
        with open(state_path, "a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            state = _load_state(handle, transcript, stat)
            _scan_appended(transcript, state)
            peak = int(state.get("peak_tokens") or 0)
            reached = max((value for value in TOKEN_MILESTONES if peak >= value), default=0)
            previous = int(state.get("notified_milestone") or 0)
            result = None
            if reached > previous:
                state["notified_milestone"] = reached
                result = (reached, peak)
            handle.seek(0)
            handle.truncate()
            json.dump(state, handle, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
            return result
    except (OSError, TypeError, ValueError):
        return None


def main():
    payload = load_payload()
    if payload.get("agent_id"):
        return
    if stop_guard_cwd(payload) is None:
        return
    if not isinstance(payload.get("session_id"), str) or not payload["session_id"]:
        return
    reached = _reached_milestone(payload)
    if reached is None:
        return
    emit_note("Stop", MEMORY_NOTE)
    log_hook_signal(
        __file__, "memory-checkpoint", "noted", 1, payload,
        context=MEMORY_NOTE,
    )


if __name__ == "__main__":
    run(main)
