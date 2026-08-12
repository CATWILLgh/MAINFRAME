#!/usr/bin/env python3
"""Contract tests for the fail-open, loud hook launcher."""

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "adapters/claude-code/plugin/hooks/scripts")
LAUNCHER = os.path.join(SCRIPTS, "run-hook.sh")
GOOD = os.path.join(SCRIPTS, "telemetry.py")
SMOKE = os.path.join(SCRIPTS, "hooklib-smoke-check.py")


def _run(event, script, tmpdir, session="session-a", extra_env=None):
    env = dict(os.environ, TMPDIR=tmpdir)
    if extra_env:
        env.update(extra_env)
    payload = json.dumps({"hook_event_name": event, "session_id": session})
    return subprocess.run(
        ["sh", LAUNCHER, event, script], input=payload,
        capture_output=True, text=True, env=env, timeout=30,
    )


def test_success_passes_through_untouched():
    with tempfile.TemporaryDirectory() as tmp:
        proc = _run("PreToolUse", GOOD, tmp)
        assert proc.returncode == 0 and proc.stdout == ""


def test_missing_script_reports_to_immediate_caller():
    with tempfile.TemporaryDirectory() as tmp:
        proc = _run("PreToolUse", "/nonexistent/hook.py", tmp)
        assert proc.returncode == 0
        obj = json.loads(proc.stdout)
        note = obj["hookSpecificOutput"]["additionalContext"]
        assert "hook.py did not complete" in note
        assert "immediate caller" in note
        assert "Tell the user" not in note
        assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert obj["systemMessage"] == note


def test_same_failure_is_once_per_session():
    with tempfile.TemporaryDirectory() as tmp:
        first = _run("Stop", "/nonexistent/hook.py", tmp, "same")
        second = _run("Stop", "/nonexistent/hook.py", tmp, "same")
        third = _run("Stop", "/nonexistent/hook.py", tmp, "other")
        assert first.stdout.strip()
        assert second.stdout == ""
        assert third.stdout.strip(), "another session needs its own notice"


def test_distinct_hook_failures_are_not_collapsed():
    with tempfile.TemporaryDirectory() as tmp:
        one = _run("Stop", "/nonexistent/one.py", tmp)
        two = _run("Stop", "/nonexistent/two.py", tmp)
        assert one.stdout.strip() and two.stdout.strip()


def test_parallel_same_failure_emits_exactly_once():
    with tempfile.TemporaryDirectory() as tmp:
        def invoke(_):
            return _run("SubagentStop", "/nonexistent/hook.py", tmp, "parallel")
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(invoke, range(32)))
        assert all(item.returncode == 0 for item in results)
        assert sum(bool(item.stdout.strip()) for item in results) == 1


def test_event_without_model_context_is_deferred_to_session_start():
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as state:
        env = {"MAINFRAME_HOOK_FAILURE_STATE_DIR": state}
        ended = _run("SessionEnd", "/nonexistent/hook.py", tmp, "ended", env)
        assert ended.returncode == 0 and ended.stdout == ""
        started = _run("SessionStart", SMOKE, tmp, "new", env)
        obj = json.loads(started.stdout)
        note = obj["hookSpecificOutput"]["additionalContext"]
        assert "hook.py did not complete during SessionEnd" in note
        again = _run("SessionStart", SMOKE, tmp, "another", env)
        assert again.stdout == "", "pending notice must be atomically consumed"


def test_missing_reporter_uses_loud_role_neutral_fallback():
    with tempfile.TemporaryDirectory() as tmp:
        copied = os.path.join(tmp, "run-hook.sh")
        shutil.copy2(LAUNCHER, copied)
        payload = json.dumps({"hook_event_name": "Stop", "session_id": "s"})
        proc = subprocess.run(
            ["sh", copied, "Stop", "/nonexistent/hook.py"], input=payload,
            capture_output=True, text=True, env=dict(os.environ, TMPDIR=tmp),
            timeout=30,
        )
        obj = json.loads(proc.stdout)
        note = obj["hookSpecificOutput"]["additionalContext"]
        assert proc.returncode == 0
        assert "failure reporter also failed" in note
        assert "immediate caller" in note and "Tell the user" not in note


def _run_all():
    failures = 0
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
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
