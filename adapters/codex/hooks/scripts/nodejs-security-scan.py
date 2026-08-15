#!/usr/bin/env python3
"""Report newly introduced high-confidence Node.js safety findings once."""

from collections import Counter
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (
        emit_note, ext, load_payload, log_hook_signal, read_git_head, run,
    )
    from _marker_state import update
    from _node_findings import finding_counts, findings, JS_EXTS
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


def _display_path(path, cwd):
    real_path = os.path.realpath(path)
    base = os.path.realpath(cwd or ".")
    try:
        if os.path.commonpath((base, real_path)) == base:
            return os.path.relpath(real_path, base)
    except (OSError, ValueError):
        pass
    return os.path.basename(real_path)


def _format(path, rows, before_counts, delta_counts, cwd):
    display_path = _display_path(path, cwd)
    by_key = {}
    for row in rows:
        by_key.setdefault(row["key"], []).append(row)
    lines = []
    for key, added_count in delta_counts.items():
        matching = by_key.get(key, [])
        if not matching or added_count <= 0:
            continue
        representative = matching[0]
        if before_counts.get(key, 0) == 0:
            lines.extend(
                f"  {display_path}:{row['row']} — "
                f"{row['code']}: {row['message']}"
                for row in matching[:added_count]
            )
        else:
            suffix = "s" if added_count != 1 else ""
            lines.append(
                f"  {display_path} — {representative['code']}: "
                f"{added_count} additional matching finding{suffix}"
            )
    if len(lines) > _MAX_ROWS:
        omitted = len(lines) - _MAX_ROWS
        lines = lines[:_MAX_ROWS]
        lines.append(f"  …and {omitted} more locations")
    return "\n".join(lines[:_MAX_ROWS + 1])


def main():
    payload = load_payload()
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "MultiEdit", "Write"):
        return
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    file_ext = ext(file_path)
    if not file_path or file_ext not in JS_EXTS or not os.path.exists(file_path):
        return

    before, after = _before_after(tool_name, tool_input, file_path)
    before_rows = findings(before, file_ext, file_path)
    after_rows = findings(after, file_ext, file_path)
    before_counts = Counter(row["key"] for row in before_rows)
    after_counts = Counter(row["key"] for row in after_rows)
    delta_counts = after_counts - before_counts
    delta_added, _, resolved = update(
        payload.get("session_id"), payload.get("agent_id"), file_path,
        dict(delta_counts), counter=finding_counts, namespace="node-delta",
        current_counts=after_counts,
    )
    if resolved:
        log_hook_signal(__file__, "node-safety", "resolved", len(resolved), payload)
    if not delta_added:
        return

    wanted = set(delta_added)
    rows = [row for row in after_rows if row["key"] in wanted]
    reported_deltas = {
        key: count for key, count in delta_counts.items() if key in wanted
    }
    count = sum(reported_deltas.values())
    note = (
        f"Node safety check found {count} new issue(s):\n"
        + _format(
            file_path, rows, before_counts, reported_deltas,
            payload.get("cwd") or os.getcwd(),
        )
        + "\nResolve the underlying code before completion; suppressing the "
        "diagnostic does not resolve it."
    )
    emit_note("PostToolUse", note)
    log_hook_signal(
        __file__, "node-safety", "noted", count, payload, context=note
    )


if __name__ == "__main__":
    run(main)
