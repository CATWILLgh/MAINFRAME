#!/usr/bin/env python3
"""Block completion on unresolved comment findings owned by this session."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _comment_findings import finding_counts, findings
    from _hooklib import (
        emit_block, ext, load_payload, log_hook_signal, run, stop_guard_cwd,
    )
    from _marker_state import unresolved
except Exception:
    sys.exit(0)

_MAX_QUOTED = 5


def _current_rows(files, keys):
    rows = []
    wanted = set(keys)
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except (FileNotFoundError, OSError):
            continue
        for key, line, value, _ in findings(text, ext(path)):
            if key in wanted:
                first = value.strip().splitlines()[0].strip()[:100]
                rows.append((os.path.basename(path), line, first))
    return rows


def main():
    payload = load_payload()
    if stop_guard_cwd(payload) is None:
        return
    session_id = payload.get("session_id")
    if not session_id:
        raise ValueError("comment stop gate requires session_id")
    agent_id = payload.get("agent_id")
    keys, files = unresolved(
        session_id, agent_id, include_subagents=not bool(agent_id),
        counter=finding_counts, namespace="comments", include_files=True,
    )
    if not keys:
        return
    rows = _current_rows(files, keys)
    quoted = "".join(
        f"  {name}:{line}: {text}\n" for name, line, text in rows[:_MAX_QUOTED]
    )
    more = f"  …and {len(rows) - _MAX_QUOTED} more\n" if len(rows) > _MAX_QUOTED else ""
    reason = (
        f"{len(keys)} unresolved comment candidate(s) introduced by this "
        "session still depend on temporary plan, phase, step, or discussion "
        "context:\n" + quoted + more +
        "Make every comment understandable from the repository alone. Preserve "
        "durable, code-relevant rationale by rewriting it; remove a comment "
        "only when it contains no durable information."
    )
    emitted_reason = emit_block(reason)
    log_hook_signal(
        __file__, "process-leakage", "blocked", len(keys), payload,
        context=emitted_reason,
    )


if __name__ == "__main__":
    run(main)
