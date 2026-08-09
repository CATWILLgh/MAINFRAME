#!/usr/bin/env python3
"""Tier-1 tests for memory-reminder.py (Stop-hook auto-memory write reminder).

The script name is hyphenated (hook convention) so it cannot be imported by
name; it is loaded by path via importlib. Tests drive main() with a controlled
stdin payload + captured stdout, and unit-test the throttle and substantive
gates directly. No real environment, no telemetry writes (log_event is stubbed).
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters/claude-code/plugin", "hooks", "scripts", "memory-reminder.py")


def _load():
    spec = importlib.util.spec_from_file_location("memory_reminder", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load()


def _drive(payload, *, throttled=False, substantive=True, with_session=True):
    """Run main() with payload on stdin; stub the gates + telemetry. Returns
    (stdout_text, logged_events)."""
    if with_session:
        payload = {"session_id": "session-main", **payload}
    out = io.StringIO()
    saved = (sys.stdin, sys.stdout,
             gate._throttled, gate._substantive, gate.log_event)
    logged = []
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.stdout = out
        gate._throttled = lambda session_id, stamp_dir=None: throttled
        gate._substantive = lambda p: substantive
        gate.log_event = lambda *a, **k: logged.append((a, k))
        gate.main()
    finally:
        (sys.stdin, sys.stdout,
         gate._throttled, gate._substantive, gate.log_event) = saved
    return out.getvalue(), logged


def test_fires_on_substantive_unthrottled():
    out, logged = _drive({"cwd": "/p", "transcript_path": "/t"},
                         throttled=False, substantive=True)
    assert out.strip(), "expected a note on a substantive, unthrottled stop"
    obj = json.loads(out)
    note = obj["hookSpecificOutput"]["additionalContext"]
    assert "auto-memory" in note
    assert obj["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert logged and logged[0][0][0] == "memory_reminder"


def test_note_is_non_blocking():
    out, _ = _drive({"cwd": "/p", "transcript_path": "/t"})
    obj = json.loads(out)
    assert "decision" not in obj, "reminder must not block the stop"
    assert "additionalContext" in obj["hookSpecificOutput"]


def _with_feedback_env(value, fn):
    saved = os.environ.get("MAINFRAME_FEEDBACK_NUDGE")
    try:
        os.environ["MAINFRAME_FEEDBACK_NUDGE"] = value
        return fn()
    finally:
        if saved is None:
            os.environ.pop("MAINFRAME_FEEDBACK_NUDGE", None)
        else:
            os.environ["MAINFRAME_FEEDBACK_NUDGE"] = saved


def test_note_carries_feedback_mention_on_dev_install():
    out, _ = _with_feedback_env(
        "1", lambda: _drive({"cwd": "/p", "transcript_path": "/t"}))
    note = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "harness-feedback" in note


def test_note_omits_feedback_on_plain_install():
    out, _ = _with_feedback_env(
        "0", lambda: _drive({"cwd": "/p", "transcript_path": "/t"}))
    note = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "harness-feedback" not in note
    assert "auto-memory" in note


def test_note_says_nothing_to_save_is_fine():
    out, _ = _drive({"cwd": "/p", "transcript_path": "/t"})
    note = json.loads(out)["hookSpecificOutput"]["additionalContext"].lower()
    assert "nothing to save" in note


def test_silent_when_throttled():
    out, logged = _drive({"cwd": "/p", "transcript_path": "/t"}, throttled=True)
    assert out == ""
    assert logged == []


def test_silent_when_not_substantive():
    out, logged = _drive({"cwd": "/p", "transcript_path": "/t"},
                         substantive=False)
    assert out == ""
    assert logged == []


def test_silent_when_stop_hook_active():
    out, logged = _drive({"cwd": "/p", "stop_hook_active": True})
    assert out == ""
    assert logged == []


def test_silent_inside_subagent():
    out, logged = _drive({
        "cwd": "/p",
        "transcript_path": "/t",
        "agent_id": "agent-123",
        "agent_type": "researcher",
    })
    assert out == ""
    assert logged == []


def test_silent_without_session_id():
    out, logged = _drive(
        {"cwd": "/p", "transcript_path": "/t"},
        with_session=False,
    )
    assert out == ""
    assert logged == []


def test_main_session_with_agent_type_still_fires():
    out, logged = _drive({
        "cwd": "/p",
        "transcript_path": "/t",
        "agent_type": "primary-profile",
    })
    assert out.strip()
    assert logged


def test_fail_safe_on_garbage_stdin():
    out = io.StringIO()
    saved = (sys.stdin, sys.stdout)
    try:
        sys.stdin = io.StringIO("not json at all {{{")
        sys.stdout = out
        gate.main()  # must not raise; empty payload -> no transcript -> no-op
    finally:
        sys.stdin, sys.stdout = saved
    assert out.getvalue() == ""


def test_throttled_unit():
    with tempfile.TemporaryDirectory() as d:
        assert gate._throttled("session-a", stamp_dir=d) is False
        assert gate._throttled("session-a", stamp_dir=d) is True


def test_throttled_is_per_session():
    with tempfile.TemporaryDirectory() as d:
        assert gate._throttled("session-a", stamp_dir=d) is False
        assert gate._throttled("session-b", stamp_dir=d) is False


def test_substantive_unit():
    with tempfile.TemporaryDirectory() as d:
        small = os.path.join(d, "small.jsonl")
        big = os.path.join(d, "big.jsonl")
        with open(small, "w") as fh:
            fh.write("x")
        with open(big, "w") as fh:
            fh.write("x" * (gate.MIN_TRANSCRIPT_BYTES + 1))
        assert gate._substantive({"transcript_path": small}) is False
        assert gate._substantive({"transcript_path": big}) is True
        assert gate._substantive({}) is False
        assert gate._substantive({"transcript_path": "/no/such/file"}) is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f" FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
