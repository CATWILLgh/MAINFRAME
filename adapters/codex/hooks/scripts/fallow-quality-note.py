#!/usr/bin/env python3
"""Record JS/TS edit scope and run Fallow's new-only audit at Stop.

PostToolUse stores only path, line number, and a short line digest. Stop builds
an in-memory unified diff from still-live lines owned by this session and its
subagents, then asks `fallow audit` to compare that scope with HEAD. Source code
is passed directly to Fallow over stdin and is never persisted by this hook.

Only findings carrying Fallow's `introduced: true` attribution are reported.
Inherited project debt, other sessions, and unrelated dirty files stay silent.
The note is advisory and bounded; a successful audit consumes its edit state so
unchanged later Stop events do not repeat the analysis or its context.
"""

import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _fallow_state import build_diff, clear, record, whole_files
    from _hooklib import (
        emit_note, load_payload, log_hook_signal, run, stop_guard_cwd,
    )
except Exception:
    sys.exit(0)


ANALYZE_TIMEOUT = 180
MAX_ROWS = 6


def _installed_fallow():
    executable = shutil.which("fallow")
    if executable:
        return executable
    raise RuntimeError(
        "Fallow quality checks are unavailable because `fallow` is missing. "
        "Install it with `npm install -g fallow`."
    )


def _run_audit(cwd, diff_text):
    command = [
        _installed_fallow(), "audit", "--root", cwd, "--base", "HEAD",
        "--diff-stdin", "--gate", "new-only", "--format", "json", "--quiet",
    ]
    try:
        process = subprocess.run(
            command, input=diff_text, capture_output=True, text=True,
            cwd=cwd, timeout=ANALYZE_TIMEOUT,
        )
    except Exception as exc:
        raise RuntimeError("Fallow quality audit failed to run") from exc
    if process.returncode not in (0, 1, 2):
        detail = (process.stderr or process.stdout).strip().splitlines()
        suffix = f": {detail[0][:240]}" if detail else ""
        raise RuntimeError(f"Fallow quality audit failed{suffix}")
    try:
        report = json.loads(process.stdout) if process.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError("Fallow quality audit returned invalid JSON") from exc
    if not isinstance(report, dict) or report.get("kind") != "audit":
        raise RuntimeError("Fallow quality audit returned an unsupported result")
    return report


def _introduced(rows):
    return [row for row in (rows or []) if isinstance(row, dict)
            and row.get("introduced") is True]


def _display_path(value, cwd):
    if not value:
        return "?"
    try:
        return os.path.relpath(value, cwd) if os.path.isabs(value) else value
    except ValueError:
        return value


def build_note(report, cwd=".", wholly_owned=None):
    """Return a bounded note and introduced counts from an audit envelope."""
    if not isinstance(report, dict) or report.get("kind") != "audit":
        return None, {}
    dead = report.get("dead_code") or {}
    complexity = report.get("complexity") or {}
    duplication = report.get("duplication") or {}
    wholly_owned = {os.path.realpath(path) for path in (wholly_owned or set())}
    unused_files = [
        finding for finding in _introduced(dead.get("unused_files"))
        if os.path.realpath(finding.get("path") or "") in wholly_owned
    ]
    categories = {
        # Unused-file findings are file-scoped and bypass Fallow's line filter.
        # Report them only when this session wrote the complete current file.
        "unused_files": unused_files,
        "cycles": _introduced(dead.get("circular_dependencies")),
        "boundaries": _introduced(
            (dead.get("boundary_violations") or [])
            + (dead.get("boundary_call_violations") or [])
        ),
        "complexity": _introduced(complexity.get("findings")),
        "duplication": _introduced(duplication.get("clone_groups")),
    }
    counts = {name: len(rows) for name, rows in categories.items()}
    if not any(counts.values()):
        return None, counts

    rows = []
    for finding in categories["unused_files"]:
        rows.append("unused file: " + _display_path(finding.get("path"), cwd))
    for finding in categories["cycles"]:
        files = [_display_path(path, cwd) for path in finding.get("files") or []]
        rows.append("import cycle: " + " -> ".join(files[:3]))
    for finding in categories["boundaries"]:
        source = finding.get("from_path") or finding.get("path")
        target = finding.get("to_path") or finding.get("callee") or "forbidden target"
        rows.append(
            f"boundary: {_display_path(source, cwd)}:{finding.get('line', '?')} "
            f"-> {_display_path(target, cwd)}"
        )
    for finding in categories["complexity"]:
        rows.append(
            f"complexity: {_display_path(finding.get('path'), cwd)}:"
            f"{finding.get('line', '?')} `{finding.get('name', '?')}` "
            f"(cyclomatic {finding.get('cyclomatic', '?')})"
        )
    for finding in categories["duplication"]:
        instances = finding.get("instances") or []
        first = instances[0] if instances else {}
        rows.append(
            f"duplication: {_display_path(first.get('file'), cwd)}:"
            f"{first.get('start_line', '?')} ({finding.get('line_count', '?')} lines)"
        )

    shown = rows[:MAX_ROWS]
    more = f"\n  …and {len(rows) - MAX_ROWS} more" if len(rows) > MAX_ROWS else ""
    note = (
        f"Fallow found {len(rows)} new quality issue(s) introduced on lines "
        "owned by this session:\n  - " + "\n  - ".join(shown) + more
        + "\nResolve findings that remain in the implementation. This audit ignores "
        "inherited project debt and unrelated dirty work; it is advisory, not a block."
    )
    return note, counts


def _stop(payload):
    cwd = stop_guard_cwd(payload)
    if cwd is None:
        return
    session_id = payload.get("session_id")
    if not session_id:
        raise ValueError("Fallow quality audit requires session_id")
    diff_text = build_diff(session_id, cwd, include_subagents=True)
    if not diff_text:
        return
    wholly_owned = whole_files(session_id, cwd, include_subagents=True)
    report = _run_audit(cwd, diff_text)
    clear(session_id, include_subagents=True)
    note, counts = build_note(report, cwd, wholly_owned)
    if not note:
        return
    emit_note("Stop", note)
    log_hook_signal(
        __file__, "fallow-delta", "noted", sum(counts.values()), payload,
        context=note,
    )


def main():
    payload = load_payload()
    if payload.get("tool_name") in ("Edit", "MultiEdit", "Write"):
        record(payload)
    else:
        _stop(payload)


if __name__ == "__main__":
    run(main)
