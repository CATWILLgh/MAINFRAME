#!/usr/bin/env python3
"""Immediate advisory for file/function length introduced by one edit.

Codex already gives the dispatcher exact before/after snapshots for a
successful file tool call. Comparing those snapshots in PostToolUse avoids
persistent session state and gives the author one bounded note at the point
where it can still help. Inherited oversized code stays silent.

The generic file check applies to every hand-authored code extension except
SQL. Python function length uses the stdlib AST. Other language-specific
structural checks belong in profile or project testing layers.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooklib import ext, log_hook_signal
from _length_check import (
    FILE_LENGTH_EXTENSIONS,
    FILE_LENGTH_THRESHOLD,
    FUNCTION_LENGTH_THRESHOLD,
    count_lines,
    over_threshold_functions,
    python_function_spans,
)


PYTHON_EXTENSIONS = frozenset({".py", ".pyi"})
MAX_LISTED = 5


def _inside(cwd, file_path):
    root = os.path.realpath(cwd)
    real = os.path.realpath(file_path)
    try:
        return os.path.commonpath((root, real)) == root
    except ValueError:
        return False


def _relative(cwd, path):
    try:
        return os.path.relpath(path, cwd)
    except ValueError:
        return path


def _function_lengths(text):
    return {
        name: end - start + 1
        for name, start, end in python_function_spans(text)
    }


def _crossings(cwd, change):
    path = str(change.get("path") or "")
    before = change.get("before")
    after = change.get("after")
    if not path or not isinstance(before, str) or not isinstance(after, str):
        return []
    if not _inside(cwd, path) or ext(path) not in FILE_LENGTH_EXTENSIONS:
        return []

    rows = []
    before_lines = count_lines(before)
    after_lines = count_lines(after)
    if before_lines <= FILE_LENGTH_THRESHOLD < after_lines:
        rows.append(
            f"file: {_relative(cwd, path)} crossed {FILE_LENGTH_THRESHOLD} "
            f"lines ({before_lines} -> {after_lines})"
        )

    if ext(path) not in PYTHON_EXTENSIONS:
        return rows
    try:
        before_functions = _function_lengths(before)
        after_functions = over_threshold_functions(after)
    except SyntaxError:
        return rows
    for name, start, _end, length in after_functions:
        previous = int(before_functions.get(name) or 0)
        if previous <= FUNCTION_LENGTH_THRESHOLD < length:
            rows.append(
                f"Python function: {_relative(cwd, path)}:{start} `{name}` "
                f"crossed {FUNCTION_LENGTH_THRESHOLD} lines "
                f"({previous} -> {length})"
            )
    return rows


def note_for_changes(cwd, changes):
    rows = []
    for change in changes:
        if isinstance(change, dict):
            rows.extend(_crossings(cwd, change))
    if not rows:
        return None, 0
    shown = rows[:MAX_LISTED]
    more = f"\n  …and {len(rows) - MAX_LISTED} more" if len(rows) > MAX_LISTED else ""
    note = (
        f"Length quality check found {len(rows)} threshold crossing(s) in the "
        "current edit:\n  - " + "\n  - ".join(shown) + more
        + "\nKeep the implementation cohesive by splitting the newly oversized "
        "file or extracting the newly oversized function when appropriate. "
        "This is advisory, not a block."
    )
    return note, len(rows)


def record_note(payload, note, count):
    log_hook_signal(
        __file__, "length-threshold", "noted", count, payload, context=note
    )
