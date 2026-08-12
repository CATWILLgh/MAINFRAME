#!/usr/bin/env python3
"""Report newly introduced or first-observed Python safety findings once."""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (
        emit_note, ext, load_payload, log_hook_signal, read_git_head, run,
    )
    from _marker_state import update
    from _python_findings import finding_counts, findings, PY_EXTS
except Exception:
    sys.exit(0)

_MAX_ROWS = 6


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _before_after(tool_name, tool_input, file_path):
    after = _read(file_path)
    if tool_name == "Edit":
        old = tool_input.get("old_string", "") or ""
        new = tool_input.get("new_string", "") or ""
        if new and new in after:
            return after.replace(new, old, 1), after
    elif tool_name == "MultiEdit":
        before = after
        for edit in reversed(tool_input.get("edits", []) or []):
            new = edit.get("new_string", "") or ""
            old = edit.get("old_string", "") or ""
            if new and new in before:
                before = before.replace(new, old, 1)
        return before, after
    elif tool_name == "Write":
        return read_git_head(file_path) or "", after
    return read_git_head(file_path) or "", after


def _format(path, rows, cwd):
    display_path = os.path.relpath(path, cwd)
    lines = [
        f"  {display_path}:{row['row']} — {row['code']}: {row['message']}"
        for row in rows[:_MAX_ROWS]
    ]
    if len(rows) > _MAX_ROWS:
        lines.append(f"  …and {len(rows) - _MAX_ROWS} more")
    return "\n".join(lines)


def main():
    payload = load_payload()
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "MultiEdit", "Write"):
        return
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    file_ext = ext(file_path)
    if not file_path or file_ext not in PY_EXTS or not os.path.exists(file_path):
        return

    before, after = _before_after(tool_name, tool_input, file_path)
    before_rows = findings(before, file_ext, file_path)
    after_rows = findings(after, file_ext, file_path)
    before_counts = Counter(row["key"] for row in before_rows)
    after_counts = Counter(row["key"] for row in after_rows)
    delta_counts = after_counts - before_counts
    session_id = payload.get("session_id")
    agent_id = payload.get("agent_id")

    delta_added, _, resolved = update(
        session_id, agent_id, file_path, dict(delta_counts),
        counter=finding_counts, namespace="python-delta",
        current_counts=after_counts,
    )
    cwd = payload.get("cwd") or os.getcwd()

    if resolved:
        log_hook_signal(
            __file__, "python-safety", "resolved", len(resolved), payload
        )

    if delta_added:
        wanted = set(delta_added)
        rows = [row for row in after_rows if row["key"] in wanted]
        note = (
            f"Python safety check found {len(delta_added)} new issue(s):\n" +
            _format(file_path, rows, cwd) +
            "\nReview and resolve the underlying code before completion; "
            "suppressing the diagnostic does not resolve it."
        )
        emit_note("PostToolUse", note)
        log_hook_signal(
            __file__, "python-safety", "noted", len(delta_added), payload,
            context=note,
        )


if __name__ == "__main__":
    run(main)
