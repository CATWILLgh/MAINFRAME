#!/usr/bin/env python3
"""Block completion on unresolved Python findings owned by this session."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (
        emit_block, ext, load_payload, log_hook_signal, run, stop_guard_cwd,
    )
    from _marker_state import unresolved
    from _python_findings import findings
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


def _rows(files, keys):
    rows = []
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except (FileNotFoundError, OSError):
            continue
        for row in _cached_findings(text, ext(path), path):
            if row["key"] not in keys:
                continue
            rows.append((path, row))
    return rows


def _format(rows, cwd):
    lines = [
        f"  {os.path.relpath(path, cwd)}:{row['row']} — "
        f"{row['code']}: {row['message']}"
        for path, row in rows[:_MAX_ROWS]
    ]
    if len(rows) > _MAX_ROWS:
        lines.append(f"  …and {len(rows) - _MAX_ROWS} more")
    return "\n".join(lines)


def main():
    payload = load_payload()
    cwd = stop_guard_cwd(payload)
    if cwd is None:
        return
    session_id = payload.get("session_id")
    if not session_id:
        raise ValueError("Python safety stop gate requires session_id")
    agent_id = payload.get("agent_id")
    include_subagents = not bool(agent_id)

    delta_keys, delta_files = unresolved(
        session_id, agent_id, include_subagents=include_subagents,
        counter=_finding_counts, namespace="python-delta", include_files=True,
    )
    if not delta_keys:
        return

    delta_rows = _rows(delta_files, delta_keys)
    reason = (
        f"Python safety gate: {len(delta_rows)} unresolved issue(s) introduced "
        "by this session:\n" + _format(delta_rows, cwd) +
        "\nResolve the underlying code before completion."
    )
    emitted_reason = emit_block(reason)
    log_hook_signal(
        __file__, "python-safety", "blocked", len(delta_rows), payload,
        context=emitted_reason,
    )


if __name__ == "__main__":
    run(main)
