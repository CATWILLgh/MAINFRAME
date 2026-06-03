#!/usr/bin/env python3
"""PostToolUse hook: flag newly-introduced suppression markers or debug residue.

Reads the PostToolUse payload from stdin, looks at the file just written/edited,
and — only for source-code files — checks whether the change *introduced* any
suppression / placeholder marker (TODO/FIXME, skipped tests, silenced type/lint
checks) or debug residue (`debugger`, `breakpoint()`, `pdb.set_trace`,
`var_dump`/`dd`, `console.debug`). If so, emits a non-blocking note.

Diff-aware: for Edit/MultiEdit it flags only markers ADDED by the change; for
Write it diffs against `git HEAD` when tracked, else scans full content. Shared
scaffolding is in `_hooklib`, the detector sets in `_markers`. Fail-safe: any
error -> exit 0, no output.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (
        CODE_EXTENSIONS, HUB_HOOK_FILES, ext, load_payload, emit_note,
        read_git_head, run,
    )
    from _markers import MARKERS, DEBUG_RESIDUE
except Exception:
    # Shared lib broken/absent -> silent no-op; a SessionStart smoke-check
    # announces the failure loudly (see _hooklib SPOF note).
    sys.exit(0)


def _added_markers(old_text, new_text, file_ext):
    """Marker / debug-residue labels whose count increased from old to new."""
    found = []
    for label, rx in MARKERS:
        if len(rx.findall(new_text)) > len(rx.findall(old_text)):
            found.append(label)
    for label, rx, exts in DEBUG_RESIDUE:
        if file_ext in exts and len(rx.findall(new_text)) > len(rx.findall(old_text)):
            found.append(label)
    return found


def _markers_in(text, file_ext):
    found = [label for label, rx in MARKERS if rx.search(text)]
    found += [label for label, rx, exts in DEBUG_RESIDUE if file_ext in exts and rx.search(text)]
    return found


def _collect(tool_name, tool_input, file_ext):
    """Return the list of newly-introduced marker / debug-residue labels."""
    if tool_name == "Edit":
        return _added_markers(
            tool_input.get("old_string", "") or "",
            tool_input.get("new_string", "") or "",
            file_ext,
        )
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", []) or []
        old = "".join(e.get("old_string", "") or "" for e in edits)
        new = "".join(e.get("new_string", "") or "" for e in edits)
        return _added_markers(old, new, file_ext)
    if tool_name == "Write":
        # Field name is `content` for the Write tool; tolerate `file_text` too.
        content = tool_input.get("content")
        if content is None:
            content = tool_input.get("file_text", "")
        new = content or ""
        old = read_git_head(tool_input.get("file_path", ""))
        if old is not None:
            return _added_markers(old, new, file_ext)
        return _markers_in(new, file_ext)
    return []


def main():
    payload = load_payload()
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    file_path = tool_input.get("file_path", "")
    file_ext = ext(file_path)
    if not file_path or file_ext not in CODE_EXTENSIONS:
        return
    if os.path.basename(file_path) in HUB_HOOK_FILES:
        return

    labels = []
    for label in _collect(tool_name, tool_input, file_ext):
        if label not in labels:
            labels.append(label)
    if not labels:
        return

    verb = "edit" if tool_name in ("Edit", "MultiEdit") else "write"
    note = (
        f"Heads-up: this {verb} introduced leftover(s) the global engineering "
        f"rules ban in completed work: {', '.join(labels)}. Suppression markers "
        "(TODO/FIXME/HACK/XXX), skipped/focused tests, and silenced type/lint "
        "checks must not be added without explicit user permission — a failing "
        "check is a contract signal to surface, not to silence. Debug residue "
        "(debugger, breakpoint(), pdb.set_trace, var_dump/dd, console.debug) is "
        "diagnostic leftover and must be removed. Resolve them, or get the "
        "user's OK, before declaring the task done."
    )
    emit_note("PostToolUse", note)


if __name__ == "__main__":
    run(main)
