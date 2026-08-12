#!/usr/bin/env python3
"""Tell the responsible code writer to remove newly introduced residue."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (CODE_EXTENSIONS, HUB_HOOK_FILES, emit_note, ext,
                          load_payload, log_hook_signal, read_git_head, run)
    from _markers import marker_counts
    from _marker_state import update
except Exception:
    sys.exit(0)


def _positive_delta(old_text, new_text, file_ext):
    old = marker_counts(old_text, file_ext)
    new = marker_counts(new_text, file_ext)
    return {label: count - old.get(label, 0) for label, count in new.items()
            if count > old.get(label, 0)}


def _collect(tool_name, tool_input, file_ext):
    if tool_name == "Edit":
        return _positive_delta(tool_input.get("old_string", "") or "",
                               tool_input.get("new_string", "") or "", file_ext)
    if tool_name == "MultiEdit":
        totals = {}
        for edit in tool_input.get("edits", []) or []:
            delta = _positive_delta(edit.get("old_string", "") or "",
                                    edit.get("new_string", "") or "", file_ext)
            for label, count in delta.items():
                totals[label] = totals.get(label, 0) + count
        return totals
    if tool_name == "Write":
        content = tool_input.get("content")
        if content is None:
            content = tool_input.get("file_text", "")
        old = read_git_head(tool_input.get("file_path", "")) or ""
        return _positive_delta(old, content or "", file_ext)
    return {}


def main():
    payload = load_payload()
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    file_ext = ext(file_path)
    if (not file_path or file_ext not in CODE_EXTENSIONS
            or os.path.basename(file_path) in HUB_HOOK_FILES):
        return

    deltas = _collect(tool_name, tool_input, file_ext)
    _, _, resolved = update(
        payload.get("session_id"), payload.get("agent_id"), file_path, deltas
    )
    if resolved:
        log_hook_signal(
            __file__, "unfinished-residue", "resolved", len(resolved), payload
        )
    if not deltas:
        return
    labels = sorted(deltas)
    note = (
        "This edit introduced disallowed unfinished-code or diagnostic "
        f"residue: {', '.join(labels)}. Replace it with the complete working "
        "behavior and the tests the task requires. Deleting the marker alone "
        "does not resolve this finding. If it only annotated an unrelated "
        "observation, revert that annotation and record the observation through "
        "the repository ticket workflow without expanding the current scope."
    )
    emit_note("PostToolUse", note)
    log_hook_signal(
        __file__, "unfinished-residue", "noted", sum(deltas.values()), payload,
        context=note,
    )


if __name__ == "__main__":
    run(main)
