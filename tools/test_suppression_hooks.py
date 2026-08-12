#!/usr/bin/env python3
"""Tests for session-attributed suppression-marker hooks."""

import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "adapters/claude-code/plugin/hooks/scripts")
SCAN_PATH = os.path.join(SCRIPTS, "scan-suppression-markers.py")
STOP_PATH = os.path.join(SCRIPTS, "stop-gate-suppression-markers.py")
sys.path.insert(0, SCRIPTS)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


scan = _load("scan_suppression_markers", SCAN_PATH)
stop = _load("stop_gate_suppression_markers", STOP_PATH)


def _drive(module, payload, state_dir):
    output = io.StringIO()
    saved_in, saved_out = sys.stdin, sys.stdout
    saved_state = os.environ.get("MAINFRAME_MARKER_STATE_DIR")
    saved_feedback = os.environ.get("MAINFRAME_FEEDBACK_NUDGE")
    try:
        os.environ["MAINFRAME_MARKER_STATE_DIR"] = state_dir
        os.environ["MAINFRAME_FEEDBACK_NUDGE"] = "0"
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.stdout = output
        module.main()
        return output.getvalue()
    finally:
        sys.stdin, sys.stdout = saved_in, saved_out
        if saved_state is None:
            os.environ.pop("MAINFRAME_MARKER_STATE_DIR", None)
        else:
            os.environ["MAINFRAME_MARKER_STATE_DIR"] = saved_state
        if saved_feedback is None:
            os.environ.pop("MAINFRAME_FEEDBACK_NUDGE", None)
        else:
            os.environ["MAINFRAME_FEEDBACK_NUDGE"] = saved_feedback


def _edit(path, old, new, state, session="s", agent=None):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(new)
    return _drive(scan, {
        "hook_event_name": "PostToolUse", "session_id": session,
        "agent_id": agent, "tool_name": "Edit",
        "tool_input": {"file_path": path, "old_string": old, "new_string": new},
    }, state)


def _stop(state, session="s", agent=None, active=False):
    return _drive(stop, {
        "hook_event_name": "SubagentStop" if agent else "Stop",
        "session_id": session, "agent_id": agent, "cwd": "/tmp",
        "stop_hook_active": active,
    }, state)


def test_introduction_orders_the_writer_to_fix_and_blocks_stop():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "code.py")
        note = _edit(path, "pass\n", "# TODO remove me\n", state)
        assert "complete working behavior" in note
        assert "Deleting the marker alone" in note
        assert "user" not in note.lower() and "approval" not in note.lower()
        blocked = json.loads(_stop(state))
        assert blocked["decision"] == "block"
        reason = blocked["reason"]
        assert "before stopping" in reason
        assert "complete working behavior" in reason
        assert "Deleting the marker alone" in reason
        assert "user" not in reason.lower() and "approval" not in reason.lower()


def test_marker_absence_clears_the_mechanical_gate():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "code.py")
        _edit(path, "pass\n", "# FIXME temporary\n", state)
        _edit(path, "# FIXME temporary\n", "pass\n", state)
        assert _stop(state) == ""


def test_multiedit_removal_cannot_mask_a_new_marker():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "code.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# TODO new location\n")
        output = _drive(scan, {
            "hook_event_name": "PostToolUse", "session_id": "s",
            "tool_name": "MultiEdit", "tool_input": {
                "file_path": path,
                "edits": [
                    {"old_string": "# TODO old location", "new_string": "done"},
                    {"old_string": "clean", "new_string": "# TODO new location"},
                ],
            },
        }, state)
        assert "TODO" in output
        assert json.loads(_stop(state))["decision"] == "block"


def test_unrelated_dirty_marker_is_not_owned_by_the_session():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        with open(os.path.join(root, "user.py"), "w", encoding="utf-8") as handle:
            handle.write("# TODO pre-existing user work\n")
        assert _stop(state) == ""


def test_state_is_isolated_by_session_and_agent_but_main_aggregates_children():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "child.py")
        _edit(path, "pass\n", "breakpoint()\n", state, session="one", agent="agent-a")
        assert _stop(state, session="two", agent="agent-a") == ""
        assert _stop(state, session="one", agent="agent-b") == ""
        assert json.loads(_stop(state, session="one", agent="agent-a"))["decision"] == "block"
        assert json.loads(_stop(state, session="one"))["decision"] == "block"


def test_stop_loop_guard_does_not_block_twice():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "code.py")
        _edit(path, "pass\n", "# XXX residue\n", state)
        assert _stop(state, active=True) == ""


def test_parallel_edits_share_state_without_lost_entries():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        env = dict(os.environ, MAINFRAME_MARKER_STATE_DIR=state,
                   MAINFRAME_FEEDBACK_NUDGE="0")
        processes = []
        for index in range(24):
            path = os.path.join(root, f"file-{index}.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# TODO remove\n")
            payload = json.dumps({
                "hook_event_name": "PostToolUse", "session_id": "parallel",
                "agent_id": "same-agent", "tool_name": "Edit",
                "tool_input": {"file_path": path, "old_string": "pass\n",
                               "new_string": "# TODO remove\n"},
            })
            processes.append((payload, subprocess.Popen(
                [sys.executable, SCAN_PATH], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)))
        outputs = [process.communicate(payload, timeout=30)
                   for payload, process in processes]
        assert all(process.returncode == 0 for _, process in processes), outputs
        result = json.loads(_stop(state, session="parallel", agent="same-agent"))
        assert result["decision"] == "block" and "TODO" in result["reason"]


def test_effectiveness_telemetry_tracks_note_block_and_real_resolution():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        db = os.path.join(root, "telemetry.db")
        path = os.path.join(root, "code.py")
        previous = os.environ.get("MAINFRAME_TELEMETRY_DB")
        os.environ["MAINFRAME_TELEMETRY_DB"] = db
        try:
            _edit(path, "pass\n", "# TODO implement\n", state)
            assert json.loads(_stop(state))["decision"] == "block"
            _edit(path, "# TODO implement\n", "value = 1\n", state)
        finally:
            if previous is None:
                os.environ.pop("MAINFRAME_TELEMETRY_DB", None)
            else:
                os.environ["MAINFRAME_TELEMETRY_DB"] = previous
        with sqlite3.connect(db) as connection:
            payloads = [json.loads(row[0]) for row in connection.execute(
                "SELECT payload FROM events WHERE event = 'hook_signal' ORDER BY id"
            ).fetchall()]
        outcomes = [payload["outcome"] for payload in payloads]
        assert outcomes == ["noted", "blocked", "resolved"]
        assert all(payload["rule_id"] == "unfinished-residue" for payload in payloads)
        assert payloads[0]["context_chars"] > 0
        assert payloads[1]["context_chars"] > 0
        assert payloads[2]["context_chars"] == 0


def test_subagent_stop_registration_contains_gate_before_telemetry():
    path = os.path.join(SCRIPTS, "..", "hooks.json")
    with open(path, encoding="utf-8") as handle:
        hooks = json.load(handle)["hooks"]["SubagentStop"][0]["hooks"]
    scripts = [item["args"][-1] for item in hooks]
    assert scripts[0].endswith("stop-gate-suppression-markers.py")
    assert scripts[1].endswith("stop-gate-comment-discipline.py")
    assert scripts[2].endswith("python-security-stop-gate.py")
    assert scripts[3].endswith("telemetry.py")


def main():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK suppression hooks — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
