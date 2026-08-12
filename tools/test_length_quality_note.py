#!/usr/bin/env python3
"""Tests for the session-delta length quality hook."""

import json
import importlib
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor


SCRIPTS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "adapters", "claude-code",
    "plugin", "hooks", "scripts",
)
HOOK = os.path.join(SCRIPTS, "length-quality-note.py")
sys.path.insert(0, SCRIPTS)
length_state = importlib.import_module("_length_state")


def _workspace():
    root = os.path.realpath(tempfile.mkdtemp())
    env = dict(os.environ, MAINFRAME_LENGTH_STATE_DIR=os.path.join(root, "state"))
    return root, env


def _write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _lines(count):
    return "".join(f"value_{index} = {index}\n" for index in range(count))


def _payload(event, root, session="session-a", agent=None, tool_use="tool-1",
             path=None, tool="Edit"):
    value = {
        "hook_event_name": event,
        "cwd": root,
        "session_id": session,
        "agent_id": agent,
        "tool_use_id": tool_use,
        "tool_name": tool,
        "tool_input": {"file_path": path} if path else {},
    }
    if event == "Stop":
        value["stop_hook_active"] = False
    return value


def _run(payload, env):
    process = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(payload), capture_output=True,
        text=True, timeout=30, env=env,
    )
    assert process.returncode == 0, process.stderr
    return process.stdout


def _successful_edit(root, env, path, before, after, *, session="session-a",
                     agent=None, tool_use="tool-1", tool="Edit"):
    if before is None:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    else:
        _write(path, before)
    assert _run(
        _payload("PreToolUse", root, session, agent, tool_use, path, tool), env
    ) == ""
    _write(path, after)
    assert _run(
        _payload("PostToolUse", root, session, agent, tool_use, path, tool), env
    ) == ""


def _stop(root, env, session="session-a", active=False):
    payload = _payload("Stop", root, session=session)
    payload["stop_hook_active"] = active
    return _run(payload, env)


def test_existing_oversized_file_stays_silent():
    root, env = _workspace()
    path = os.path.join(root, "legacy.go")
    _successful_edit(root, env, path, _lines(405), _lines(406))
    assert _stop(root, env) == ""


def test_file_threshold_crossing_is_reported_for_non_python():
    root, env = _workspace()
    path = os.path.join(root, "service.go")
    _successful_edit(root, env, path, _lines(399), _lines(402))
    output = _stop(root, env)
    assert "service.go" in output and "399 -> 402" in output


def test_new_oversized_file_is_reported_from_zero():
    root, env = _workspace()
    path = os.path.join(root, "new.rs")
    _successful_edit(root, env, path, None, _lines(405), tool="Write")
    output = _stop(root, env)
    assert "new.rs" in output and "0 -> 405" in output


def test_vue_crossing_is_checked_now_that_inherited_files_are_silent():
    root, env = _workspace()
    path = os.path.join(root, "Large.vue")
    _successful_edit(root, env, path, _lines(399), _lines(401))
    assert "Large.vue" in _stop(root, env)


def test_sql_is_excluded_from_generic_file_length():
    root, env = _workspace()
    path = os.path.join(root, "migration.sql")
    _successful_edit(root, env, path, _lines(399), _lines(450))
    assert _stop(root, env) == ""


def test_python_function_crossing_is_reported():
    root, env = _workspace()
    path = os.path.join(root, "service.py")
    before = "def run():\n" + "    value = 1\n" * 58
    after = "def run():\n" + "    value = 1\n" * 61
    _successful_edit(root, env, path, before, after)
    output = _stop(root, env)
    assert "Python function" in output and "`run`" in output
    assert "59 -> 62" in output


def test_existing_oversized_python_function_stays_silent():
    root, env = _workspace()
    path = os.path.join(root, "legacy.py")
    before = "def run():\n" + "    value = 1\n" * 65
    after = before + "    return value\n"
    _successful_edit(root, env, path, before, after)
    assert _stop(root, env) == ""


def test_unparseable_python_baseline_does_not_guess_function_ownership():
    root, env = _workspace()
    path = os.path.join(root, "broken.py")
    before = "def broken(:\n" + _lines(399)
    after = "def repaired():\n" + "    value = 1\n" * 61 + _lines(340)
    _successful_edit(root, env, path, before, after)
    output = _stop(root, env)
    assert "file:" in output
    assert "Python function" not in output


def test_failed_edit_baseline_is_never_promoted():
    root, env = _workspace()
    path = os.path.join(root, "failed.go")
    _write(path, _lines(399))
    _run(_payload("PreToolUse", root, path=path), env)
    _write(path, _lines(450))
    assert _stop(root, env) == ""


def test_other_session_is_not_attributed():
    root, env = _workspace()
    path = os.path.join(root, "foreign.go")
    _successful_edit(
        root, env, path, _lines(399), _lines(405), session="session-b"
    )
    assert _stop(root, env, session="session-a") == ""


def test_main_session_aggregates_subagent_crossing():
    root, env = _workspace()
    path = os.path.join(root, "child.go")
    _successful_edit(
        root, env, path, _lines(399), _lines(405), agent="agent-1"
    )
    assert "child.go" in _stop(root, env)


def test_parallel_confirmations_do_not_lose_baselines():
    root, env = _workspace()
    os.environ["MAINFRAME_LENGTH_STATE_DIR"] = env["MAINFRAME_LENGTH_STATE_DIR"]
    payloads = []
    for index in range(24):
        path = os.path.join(root, "parallel", f"file-{index}.go")
        _write(path, _lines(399))
        payloads.append(_payload(
            "PreToolUse", root, tool_use=f"tool-{index}", path=path
        ))
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(length_state.capture, payloads))
    confirmations = [dict(payload, hook_event_name="PostToolUse") for payload in payloads]
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(length_state.confirm, confirmations))
    assert len(length_state.baselines("session-a", include_subagents=True)) == 24


def test_repeat_stop_is_silent_after_state_is_consumed():
    root, env = _workspace()
    path = os.path.join(root, "once.go")
    _successful_edit(root, env, path, _lines(399), _lines(405))
    assert "once.go" in _stop(root, env)
    assert _stop(root, env) == ""


def test_stop_loop_guard_preserves_silence():
    root, env = _workspace()
    path = os.path.join(root, "guard.go")
    _successful_edit(root, env, path, _lines(399), _lines(405))
    assert _stop(root, env, active=True) == ""


def main():
    tests = [function for name, function in sorted(globals().items())
             if name.startswith("test_") and callable(function)]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK length delta hook — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
