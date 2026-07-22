#!/usr/bin/env python3
"""Characterization tests for the comment-discipline-reminder PostToolUse hook.

Pins `main`'s observable behavior before any refactor, via subprocess with the
real hook payload on stdin (the hyphenated filename rules out plain import):
targeted process-leakage callout vs generic added-comment nudge vs silence,
per-edit attribution (a pre-existing marker must not re-fire), self-file and
non-code skips. Telemetry is redirected to a temp DB via MAINFRAME_TELEMETRY_DB.

Run: `python3 tools/test_comment_discipline_reminder.py` (exit 0 = pass).
Stdlib only.
"""

import json
import os
import subprocess
import sys
import tempfile

_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "dist", "claude-code", "plugin", "hooks", "scripts",
                       "comment-discipline-reminder.py")


def _run_hook(payload, tmpdir):
    config = os.path.join(tmpdir, "diagnostics.json")
    with open(config, "w", encoding="utf-8") as fh:
        json.dump({"schema_version": 1, "events": True}, fh)
    env = dict(
        os.environ,
        MAINFRAME_TELEMETRY_DB=os.path.join(tmpdir, "telemetry.db"),
        MAINFRAME_DIAGNOSTICS_CONFIG=config,
    )
    proc = subprocess.run([sys.executable, _SCRIPT], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30, env=env)
    assert proc.returncode == 0
    return proc.stdout


def _write(tmpdir, name, text):
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def test_targeted_callout_on_added_phase_marker():
    d = tempfile.mkdtemp()
    path = _write(d, "a.py", "x = 1\n# === Phase B ===\ny = 2\n")
    out = _run_hook({"tool_name": "Edit", "tool_input": {
        "file_path": path, "old_string": "x = 1\ny = 2\n",
        "new_string": "x = 1\n# === Phase B ===\ny = 2\n"}}, d)
    assert "Process-leakage" in out
    assert "# === Phase B ===" in out          # offending line quoted verbatim
    assert "Heads-up" not in out               # targeted overrides generic


def test_targeted_callout_on_docstring_ephemeral_reference():
    d = tempfile.mkdtemp()
    content = 'def f():\n    """Validate input as discussed."""\n'
    path = _write(d, "g.py", content)
    out = _run_hook({"tool_name": "Write", "tool_input": {
        "file_path": path, "content": content}}, d)
    assert "Process-leakage" in out


def test_generic_nudge_on_plain_added_comment():
    d = tempfile.mkdtemp()
    path = _write(d, "b.py", "x = 1\n# guards against double-init\ny = 2\n")
    out = _run_hook({"tool_name": "Edit", "tool_input": {
        "file_path": path, "old_string": "x = 1\ny = 2\n",
        "new_string": "x = 1\n# guards against double-init\ny = 2\n"}}, d)
    assert "added 1 new comment" in out
    assert "Process-leakage" not in out


def test_write_without_git_counts_all_comments():
    d = tempfile.mkdtemp()
    content = "# one\n# two\nx = 1\n"
    path = _write(d, "w.py", content)
    out = _run_hook({"tool_name": "Write", "tool_input": {
        "file_path": path, "content": content}}, d)
    assert "added 2 new comments" in out


def test_silent_when_no_comment_added():
    d = tempfile.mkdtemp()
    path = _write(d, "c.py", "x = 1\nz = 3\n")
    out = _run_hook({"tool_name": "Edit", "tool_input": {
        "file_path": path, "old_string": "x = 1\n",
        "new_string": "x = 1\nz = 3\n"}}, d)
    assert out.strip() == ""


def test_preexisting_marker_does_not_refire():
    # Attribution is per-edit: the marker sits in both reconstructed before
    # and after, so an edit elsewhere in the file must stay silent.
    d = tempfile.mkdtemp()
    path = _write(d, "h.py", "# === Phase B ===\nx = 1\ny = 3\n")
    out = _run_hook({"tool_name": "Edit", "tool_input": {
        "file_path": path, "old_string": "y = 2", "new_string": "y = 3"}}, d)
    assert out.strip() == ""


def test_silent_on_non_code_extension():
    d = tempfile.mkdtemp()
    out = _run_hook({"tool_name": "Edit", "tool_input": {
        "file_path": os.path.join(d, "n.md"),
        "old_string": "a", "new_string": "# b"}}, d)
    assert out.strip() == ""


def test_silent_on_other_tool_names():
    d = tempfile.mkdtemp()
    out = _run_hook({"tool_name": "Read", "tool_input": {
        "file_path": os.path.join(d, "a.py")}}, d)
    assert out.strip() == ""


def test_silent_on_self_files():
    d = tempfile.mkdtemp()
    content = "# === Phase B ===\n"
    path = _write(d, "comment_extract.py", content)
    out = _run_hook({"tool_name": "Write", "tool_input": {
        "file_path": path, "content": content}}, d)
    assert out.strip() == ""


def _run_all():
    failures = 0
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            fn()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
