#!/usr/bin/env python3
"""Block completion on unresolved Node.js findings owned by this session."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_block, ext, load_payload, log_hook_signal, run, stop_guard_cwd
    from _marker_state import unresolved
    from _node_findings import findings
except Exception:
    sys.exit(0)

_MAX_ROWS = 8
_CACHE = {}


def _cached_findings(text, file_ext, file_path):
    key = (file_path, text)
    if key not in _CACHE:
        _CACHE[key] = findings(text, file_ext, file_path)
    return _CACHE[key]


def _finding_counts(text, file_ext, file_path=None):
    counts = {}
    for row in _cached_findings(text, file_ext, file_path):
        counts[row["key"]] = counts.get(row["key"], 0) + 1
    return counts


def _display_path(path, cwd):
    real_path = os.path.realpath(path)
    base = os.path.realpath(cwd or ".")
    try:
        if os.path.commonpath((base, real_path)) == base:
            return os.path.relpath(real_path, base)
    except (OSError, ValueError):
        pass
    return os.path.basename(real_path)


def _current_findings(details, cwd):
    locations = []
    total = 0
    for path, baselines in details.items():
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except (FileNotFoundError, OSError):
            continue
        by_key = {}
        for row in _cached_findings(text, ext(path), path):
            by_key.setdefault(row["key"], []).append(row)
        display_path = _display_path(path, cwd)
        for key, baseline in baselines.items():
            rows = by_key.get(key, [])
            owned = max(0, len(rows) - int(baseline))
            if not owned:
                continue
            total += owned
            if int(baseline) == 0:
                locations.extend(
                    f"{display_path}:{row['row']} — "
                    f"{row['code']}: {row['message']}"
                    for row in rows
                )
            else:
                representative = rows[0]
                suffix = "s" if owned != 1 else ""
                locations.append(
                    f"{display_path} — {representative['code']}: "
                    f"{owned} additional matching finding{suffix}"
                )
    return locations, total


def main():
    payload = load_payload()
    cwd = stop_guard_cwd(payload)
    if cwd is None:
        return
    session_id = payload.get("session_id")
    if not session_id:
        raise ValueError("Node safety stop gate requires session_id")
    agent_id = payload.get("agent_id")
    details = unresolved(
        session_id, agent_id, include_subagents=not bool(agent_id),
        counter=_finding_counts, namespace="node-delta", include_details=True,
    )
    if not details:
        return
    locations, count = _current_findings(details, cwd)
    if not count:
        return
    lines = [f"  {location}" for location in locations[:_MAX_ROWS]]
    if len(locations) > _MAX_ROWS:
        lines.append(f"  …and {len(locations) - _MAX_ROWS} more locations")
    reason = (
        f"Node safety gate: {count} unresolved issue(s) introduced by this "
        "session:\n" + "\n".join(lines)
        + "\nResolve the underlying code before completion."
    )
    emitted_reason = emit_block(reason)
    log_hook_signal(
        __file__, "node-safety", "blocked", count, payload,
        context=emitted_reason,
    )


if __name__ == "__main__":
    run(main)
