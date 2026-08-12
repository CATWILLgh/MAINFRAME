#!/usr/bin/env python3
"""Advisory note for file/function length introduced by the current session.

PreToolUse captures line counts and Python function spans before a file tool
runs. PostToolUse confirms that baseline only after a successful edit. Stop
compares the earliest confirmed baseline from the main session and its
subagents with current content, then consumes the state.

The generic file check applies to every hand-authored code extension except
SQL. Python function length uses the stdlib AST. JS/TS structural quality is
covered separately by the delta-aware Fallow audit; other language-specific
function parsers belong in future profile/project testing layers.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (
        emit_note, ext, load_payload, log_hook_signal, run, stop_guard_cwd,
    )
    from _length_check import (
        FILE_LENGTH_EXTENSIONS, FILE_LENGTH_THRESHOLD,
        FUNCTION_LENGTH_THRESHOLD, count_lines, over_threshold_functions,
    )
    from _length_state import baselines, capture, clear, confirm
except Exception:
    sys.exit(0)


PYTHON_EXTENSIONS = frozenset({".py", ".pyi"})
MAX_LISTED = 5


def _inside(cwd, file_path):
    root = os.path.realpath(cwd)
    real = os.path.realpath(file_path)
    try:
        return os.path.commonpath((root, real)) == root
    except ValueError:
        return False


def _scan(cwd, snapshots):
    """Return only threshold crossings introduced after stored baselines."""
    file_over = []
    function_over = []
    for file_path, baseline in sorted(snapshots.items()):
        if not _inside(cwd, file_path) or not os.path.isfile(file_path):
            continue
        if ext(file_path) not in FILE_LENGTH_EXTENSIONS:
            continue
        try:
            with open(file_path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        current_lines = count_lines(text)
        baseline_lines = int(baseline.get("lines") or 0)
        if baseline_lines <= FILE_LENGTH_THRESHOLD < current_lines:
            file_over.append((file_path, baseline_lines, current_lines))
        if ext(file_path) not in PYTHON_EXTENSIONS:
            continue
        baseline_functions = baseline.get("functions")
        if not isinstance(baseline_functions, dict):
            continue
        try:
            current_functions = over_threshold_functions(text)
        except SyntaxError:
            continue
        for name, start, _end, length in current_functions:
            before = int(baseline_functions.get(name) or 0)
            if before <= FUNCTION_LENGTH_THRESHOLD < length:
                function_over.append((file_path, name, start, before, length))
    return file_over, function_over


def _relative(cwd, path):
    try:
        return os.path.relpath(path, cwd)
    except ValueError:
        return path


def _format_note(cwd, file_over, function_over):
    rows = []
    for path, before, after in file_over:
        rows.append(
            f"file: {_relative(cwd, path)} crossed {FILE_LENGTH_THRESHOLD} "
            f"lines ({before} -> {after})"
        )
    for path, name, start, before, after in function_over:
        rows.append(
            f"Python function: {_relative(cwd, path)}:{start} `{name}` crossed "
            f"{FUNCTION_LENGTH_THRESHOLD} lines ({before} -> {after})"
        )
    shown = rows[:MAX_LISTED]
    more = f"\n  …and {len(rows) - MAX_LISTED} more" if len(rows) > MAX_LISTED else ""
    return (
        f"Length quality check found {len(rows)} threshold crossing(s) introduced "
        "by this session:\n  - " + "\n  - ".join(shown) + more
        + "\nKeep the implementation cohesive by splitting the newly oversized "
        "file or extracting the newly oversized function when appropriate. "
        "This is advisory, not a block."
    )


def _stop(payload):
    cwd = stop_guard_cwd(payload)
    if cwd is None:
        return
    session_id = payload.get("session_id")
    if not session_id:
        raise ValueError("length quality check requires session_id")
    snapshots = baselines(session_id, include_subagents=True)
    if not snapshots:
        return
    file_over, function_over = _scan(cwd, snapshots)
    clear(session_id, include_subagents=True)
    if file_over or function_over:
        note = _format_note(cwd, file_over, function_over)
        emit_note("Stop", note)
        log_hook_signal(
            __file__, "length-threshold", "noted",
            len(file_over) + len(function_over), payload, context=note,
        )


def main():
    payload = load_payload()
    event = payload.get("hook_event_name")
    if event == "PreToolUse":
        capture(payload)
    elif event == "PostToolUse":
        confirm(payload)
    else:
        _stop(payload)


if __name__ == "__main__":
    run(main)
