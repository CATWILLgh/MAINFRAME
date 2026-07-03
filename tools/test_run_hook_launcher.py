#!/usr/bin/env python3
"""Tests for run-hook.sh — the hook launcher that converts interpreter-level
launch failures into a LOUD no-op instead of an exit-2 tool block.

Contract under test (WeBuy 2026-06-20 outage): python3 exits 2 when it cannot
open the script file, and the hooks contract reads exit 2 on PreToolUse as
BLOCK — so an unreadable script froze every Bash call. The launcher must (a)
change nothing on success, (b) emit a degradation notice (additionalContext +
systemMessage) and exit 0 on launch failure, (c) throttle the notice to once
per parent process via a latch, (d) stay loud when the latch dir is unusable.
"""

import json
import os
import stat
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(HERE, "..", "plugin-dist", "hooks", "scripts", "run-hook.sh")
GOOD = os.path.join(HERE, "..", "plugin-dist", "hooks", "scripts", "telemetry.py")


def _run(event, script, tmpdir, stdin="{}"):
    env = dict(os.environ, TMPDIR=tmpdir)
    return subprocess.run(["sh", LAUNCHER, event, script],
                          input=stdin, capture_output=True, text=True,
                          env=env, timeout=30)


def test_success_passes_through_untouched():
    tmp = tempfile.mkdtemp()
    proc = _run("PreToolUse", GOOD, tmp, stdin=json.dumps(
        {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {}}))
    assert proc.returncode == 0
    assert "DEGRADATION" not in proc.stdout


def test_missing_script_notices_and_exits_zero():
    tmp = tempfile.mkdtemp()
    proc = _run("PreToolUse", "/nonexistent/hook.py", tmp)
    assert proc.returncode == 0, "launch failure must not exit nonzero (2 = block)"
    obj = json.loads(proc.stdout)
    assert "DEGRADATION" in obj["hookSpecificOutput"]["additionalContext"]
    assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "systemMessage" in obj and "hook.py" in obj["systemMessage"]


def test_latch_throttles_second_notice():
    tmp = tempfile.mkdtemp()
    first = _run("Stop", "/nonexistent/hook.py", tmp)
    second = _run("Stop", "/nonexistent/hook.py", tmp)
    assert "systemMessage" in first.stdout
    assert second.returncode == 0 and second.stdout.strip() == ""


def test_unusable_latch_dir_stays_loud():
    # Total-outage shape: if even the latch cannot be probed/created, every
    # call notices — loud is correct when a restart is needed anyway.
    tmp = tempfile.mkdtemp()
    locked = os.path.join(tmp, "locked")
    os.mkdir(locked)
    os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
    try:
        first = _run("Stop", "/nonexistent/hook.py", locked)
        second = _run("Stop", "/nonexistent/hook.py", locked)
        assert "systemMessage" in first.stdout
        assert "systemMessage" in second.stdout, "no latch -> notice every call"
    finally:
        os.chmod(locked, stat.S_IRWXU)


def _run_all():
    import sys
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
