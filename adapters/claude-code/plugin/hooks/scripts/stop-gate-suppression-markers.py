#!/usr/bin/env python3
"""Block completion on unresolved residue introduced by this session."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (
        emit_block, load_payload, log_hook_signal, run, stop_guard_cwd,
    )
    from _marker_state import unresolved
except Exception:
    sys.exit(0)


def main():
    payload = load_payload()
    if stop_guard_cwd(payload) is None:
        return
    session_id = payload.get("session_id")
    if not session_id:
        raise ValueError("marker stop gate requires session_id")
    agent_id = payload.get("agent_id")
    labels = unresolved(
        session_id, agent_id,
        include_subagents=not bool(agent_id),
    )
    if not labels:
        return
    reason = (
        "Unresolved unfinished-code or diagnostic residue introduced by this "
        f"session remains: {', '.join(labels)}. Replace it with the complete "
        "working behavior and the tests the task requires before stopping. "
        "Deleting the marker alone is not a valid resolution. If it only "
        "annotated an unrelated observation, revert that annotation and record "
        "the observation through the repository ticket workflow without "
        "expanding the current scope."
    )
    emitted_reason = emit_block(reason)
    log_hook_signal(
        __file__, "unfinished-residue", "blocked", len(labels), payload,
        context=emitted_reason,
    )


if __name__ == "__main__":
    run(main)
