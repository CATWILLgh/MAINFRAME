#!/usr/bin/env python3
"""Main-session Stop hook: advisory reminder to persist durable facts to
Claude Code's native auto-memory.

Recall is automatic (the harness injects relevant memories into context);
WRITING is model-discretion, and that is the reliability gap this nudges. The
note is NON-blocking (a Stop `additionalContext`, never a block) so it reminds
without coercing — "nothing to save" is an expected, fine outcome. A coercive
nudge that keeps firing on empty sessions trains the model to ignore it (hub
lesson: the oxlint react-perf false-positive firehose); the opt-out framing is
the guard against that.

Throttled to ~once per THROTTLE_SECONDS per project and silent on trivial
sessions (transcript below MIN_TRANSCRIPT_BYTES), so it surfaces a handful of
times across a long, multi-compact run rather than every turn.

Why Stop and not a compaction hook: PreCompact gives the model no turn, and no
hook exposes context-fill, so timing a write "just before compaction" is
impossible — Stop is the only event handing the model a mid-flow turn (and it
fires in unattended auto-mode too). Coverage is therefore probabilistic, not
guaranteed. See ADR 0080.

Fail-safe: any error -> exit 0 (no-op).
"""

import hashlib
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (emit_note, feedback_skill_installed, load_payload,
                          log_event, run, stop_guard_cwd)
except Exception:
    sys.exit(0)

THROTTLE_SECONDS = 1800
MIN_TRANSCRIPT_BYTES = 50_000

MEMORY_NOTE = (
    "Memory check (skip if nothing applies): did a durable, reusable fact "
    "surface this session — a user preference, a project constraint, a "
    "hard-won gotcha — that a future session would want? If so, save it to "
    "your auto-memory now, before older context is compacted away. Recall is "
    "automatic; writing is your initiative. Nothing to save is a fine answer."
)
# Dev-only: a plain clone has no harness-feedback skill to file to (gated like FEEDBACK_NUDGE).
FEEDBACK_TAIL = (
    " If the mainframe harness itself got in your way this session, file it "
    "via the harness-feedback skill."
)


def _note():
    return MEMORY_NOTE + (FEEDBACK_TAIL if feedback_skill_installed() else "")


def _throttled(cwd, stamp_dir=None):
    """True when this project nudged within THROTTLE_SECONDS; stamps otherwise."""
    d = stamp_dir or tempfile.gettempdir()
    key = hashlib.sha256(cwd.encode("utf-8", "replace")).hexdigest()[:16]
    stamp = os.path.join(d, f"memory-reminder-{key}.stamp")
    try:
        if time.time() - os.path.getmtime(stamp) < THROTTLE_SECONDS:
            return True
    except OSError:
        pass
    try:
        with open(stamp, "w") as fh:
            fh.write(str(int(time.time())))
    except OSError:
        pass
    return False


def _substantive(payload):
    """True when the transcript is large enough to plausibly hold a
    memory-worthy fact — a cheap byte-size proxy that skips trivial sessions."""
    path = payload.get("transcript_path")
    if not path:
        return False
    try:
        return os.path.getsize(os.path.expanduser(path)) >= MIN_TRANSCRIPT_BYTES
    except OSError:
        return False


def main():
    payload = load_payload()
    if payload.get("agent_id"):
        return
    cwd = stop_guard_cwd(payload)
    if cwd is None:
        return
    if not _substantive(payload):
        return
    if _throttled(cwd):
        return
    emit_note("Stop", _note())
    log_event("memory_reminder", {"trigger": "stop"}, payload)


if __name__ == "__main__":
    run(main)
