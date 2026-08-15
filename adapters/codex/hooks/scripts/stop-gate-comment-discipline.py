#!/usr/bin/env python3
"""Block completion on unresolved comment findings owned by this session."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _comment_findings import display_path, finding_counts, findings
    from _hooklib import (
        emit_block, ext, load_payload, log_hook_signal, run, stop_guard_cwd,
    )
    from _marker_state import unresolved
except Exception:
    sys.exit(0)

_MAX_QUOTED = 5


def _current_locations(details, cwd):
    locations = []
    count = 0
    for path, baselines in details.items():
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except (FileNotFoundError, OSError):
            continue
        by_key = {}
        for key, line, _, kind in findings(text, ext(path)):
            by_key.setdefault(key, []).append((line, kind))
        name = display_path(path, cwd)
        for key, baseline in baselines.items():
            rows = by_key.get(key, [])
            owned = max(0, len(rows) - int(baseline))
            count += owned
            if baseline == 0:
                locations.extend(
                    f"{name}:{line} ({kind})" for line, kind in rows
                )
            elif owned:
                plural = "s" if owned != 1 else ""
                locations.append(
                    f"{name} ({owned} matching comment candidate{plural})"
                )
    return locations, count


def main():
    payload = load_payload()
    if stop_guard_cwd(payload) is None:
        return
    session_id = payload.get("session_id")
    if not session_id:
        raise ValueError("comment stop gate requires session_id")
    agent_id = payload.get("agent_id")
    details = unresolved(
        session_id, agent_id, include_subagents=not bool(agent_id),
        counter=finding_counts, namespace="comments", include_details=True,
    )
    if not details:
        return
    current, count = _current_locations(details, payload.get("cwd"))
    if not count:
        return
    suffix = "s" if count != 1 else ""
    locations = "".join(f"  {location}\n" for location in current[:_MAX_QUOTED])
    more = (
        f"  …and {len(current) - _MAX_QUOTED} more\n"
        if len(current) > _MAX_QUOTED else ""
    )
    reason = (
        f"{count} unresolved comment candidate{suffix} introduced by this "
        "session still depend on temporary plan, phase, step, or discussion "
        "context:\n" + locations + more +
        "Make every comment understandable from the repository alone. Preserve "
        "durable, code-relevant rationale by rewriting it; remove a comment "
        "only when it contains no durable information."
    )
    emitted_reason = emit_block(reason)
    log_hook_signal(
        __file__, "process-leakage", "blocked", count, payload,
        context=emitted_reason,
    )


if __name__ == "__main__":
    run(main)
