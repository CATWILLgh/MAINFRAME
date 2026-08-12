#!/usr/bin/env python3
"""Deduplicate and deliver role-neutral infrastructure hook failures."""

import hashlib
import json
import os
import sys
import tempfile
import time


_MODEL_CONTEXT_EVENTS = {
    "SessionStart", "UserPromptExpansion", "UserPromptSubmit", "PreToolUse",
    "PostToolUse", "PostToolUseFailure", "Stop", "SubagentStart",
    "SubagentStop", "PreCompact", "Setup",
}
_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def _payload():
    try:
        value = json.load(sys.stdin)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _safe_name(path):
    return os.path.basename(path) or "hook"


def _failure_text(event, script, status):
    return (
        f"MAINFRAME hook failure: {_safe_name(script)} did not complete during "
        f"{event} (exit {status}). The check it provides is unavailable. "
        "Return this exact failure to your immediate caller before claiming "
        "the affected operation or task is verified. Do not retry or repair "
        "MAINFRAME unless assigned."
    )


def _state_root():
    return os.environ.get(
        "MAINFRAME_HOOK_FAILURE_STATE_DIR",
        os.path.expanduser("~/.claude/mainframe/state/hook-failures"),
    )


def _latch_root():
    return os.path.join(
        os.environ.get("TMPDIR", tempfile.gettempdir()),
        "mainframe-hook-failure-latches",
    )


def _cleanup(directory):
    try:
        cutoff = time.time() - _MAX_AGE_SECONDS
        for name in os.listdir(directory):
            path = os.path.join(directory, name)
            if os.path.getmtime(path) < cutoff:
                if os.path.isdir(path):
                    os.rmdir(path)
                else:
                    os.unlink(path)
    except OSError:
        pass


def _claim(signature):
    root = _latch_root()
    os.makedirs(root, mode=0o700, exist_ok=True)
    _cleanup(root)
    path = os.path.join(root, hashlib.sha256(signature.encode()).hexdigest())
    try:
        os.mkdir(path, mode=0o700)
        return True
    except FileExistsError:
        return False


def _persist_pending(signature, text):
    root = _state_root()
    os.makedirs(root, mode=0o700, exist_ok=True)
    key = hashlib.sha256(signature.encode()).hexdigest()
    final = os.path.join(root, key + ".json")
    fd, temp = tempfile.mkstemp(prefix=".pending-", dir=root, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"message": text}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, final)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def main():
    event, script, status, parent_pid = sys.argv[1:5]
    payload = _payload()
    session = str(payload.get("session_id") or f"parent-{parent_pid}")
    signature = "\0".join((session, event, os.path.abspath(script), status))
    if not _claim(signature):
        return

    text = _failure_text(event, script, status)
    if event not in _MODEL_CONTEXT_EVENTS:
        _persist_pending(signature, text)
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        },
        "systemMessage": text,
    }))


if __name__ == "__main__":
    main()
