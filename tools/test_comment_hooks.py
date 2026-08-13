#!/usr/bin/env python3
"""Tests for session-attributed comment-discipline hooks."""

import importlib.util
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "adapters/claude-code/plugin/hooks/scripts")
REMINDER_PATH = os.path.join(SCRIPTS, "comment-discipline-reminder.py")
STOP_PATH = os.path.join(SCRIPTS, "stop-gate-comment-discipline.py")
sys.path.insert(0, SCRIPTS)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reminder = _load("comment_discipline_reminder", REMINDER_PATH)
stop = _load("stop_gate_comment_discipline", STOP_PATH)


def _drive(module, payload, state_dir):
    output = io.StringIO()
    saved_in, saved_out = sys.stdin, sys.stdout
    saved_state = os.environ.get("MAINFRAME_MARKER_STATE_DIR")
    saved_notice_state = os.environ.get("MAINFRAME_NOTICE_STATE_DIR")
    saved_feedback = os.environ.get("MAINFRAME_FEEDBACK_NUDGE")
    try:
        os.environ["MAINFRAME_MARKER_STATE_DIR"] = state_dir
        os.environ["MAINFRAME_NOTICE_STATE_DIR"] = state_dir + "-notices"
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
        if saved_notice_state is None:
            os.environ.pop("MAINFRAME_NOTICE_STATE_DIR", None)
        else:
            os.environ["MAINFRAME_NOTICE_STATE_DIR"] = saved_notice_state
        if saved_feedback is None:
            os.environ.pop("MAINFRAME_FEEDBACK_NUDGE", None)
        else:
            os.environ["MAINFRAME_FEEDBACK_NUDGE"] = saved_feedback


def _edit(path, old, new, state, session="s", agent=None):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(new)
    return _drive(reminder, {
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


def test_every_new_comment_gets_a_short_review_reminder():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "code.py")
        note = _edit(path, "value = 1\n",
                     "# Retry once because duplicate requests are billable.\nvalue = 1\n",
                     state)
        assert "Every comment must preserve durable" in note
        assert "Do not discard useful rationale" in note
        assert _stop(state) == ""


def test_generic_reminder_is_once_per_session_and_writer():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        first = os.path.join(root, "first.py")
        second = os.path.join(root, "second.py")
        comment = "# Retry once because duplicate requests are billable.\nvalue = 1\n"
        assert "Every comment must preserve durable" in _edit(
            first, "value = 1\n", comment, state, session="one", agent="writer"
        )
        assert _edit(
            second, "value = 1\n", comment, state, session="one", agent="writer"
        ) == ""
        assert _edit(
            second, "value = 1\n", comment, state, session="one", agent="other"
        )
        assert _edit(
            second, "value = 1\n", comment, state, session="two", agent="writer"
        )


def test_suppression_marker_does_not_receive_a_duplicate_generic_reminder():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "code.py")
        note = _edit(path, "value = 1\n", "# TODO: implement later\nvalue = 1\n",
                     state)
        assert note == ""
        assert _stop(state) == ""


def test_other_comments_in_same_edit_still_receive_the_generic_reminder():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "code.py")
        note = _edit(
            path,
            "value = 1\n",
            "# TODO: implement later\n"
            "# Retry once because duplicate requests are billable.\n"
            "value = 1\n",
            state,
        )
        assert "Review the 1 new comment." in note


def test_transient_comment_is_quoted_and_blocks_only_its_writer():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "code.py")
        note = _edit(path, "value = 1\n", "# Phase 2: wire the API\nvalue = 1\n",
                     state, session="one", agent="writer")
        assert "repository alone" in note and "Phase 2" in note
        assert "remove it only when it contains no durable information" in note
        assert _stop(state, session="two", agent="writer") == ""
        assert _stop(state, session="one", agent="other") == ""
        blocked = json.loads(_stop(state, session="one", agent="writer"))
        assert blocked["decision"] == "block"
        assert "Preserve durable" in blocked["reason"]


def test_rewriting_to_durable_rationale_clears_the_gate():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "code.py")
        transient = "# Step 1: retry\nvalue = 1\n"
        _edit(path, "value = 1\n", transient, state)
        durable = "# Retry once because duplicate requests are billable.\nvalue = 1\n"
        _edit(path, transient, durable, state)
        assert _stop(state) == ""


def test_unrelated_dirty_comment_is_not_attributed():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        with open(os.path.join(root, "other.py"), "w", encoding="utf-8") as handle:
            handle.write("# Phase 4: pre-existing user work\n")
        assert _stop(state) == ""


def test_main_session_aggregates_unresolved_child_findings():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "child.py")
        _edit(path, "value = 1\n", "# Step 3: finish\nvalue = 1\n", state,
              session="one", agent="child")
        assert json.loads(_stop(state, session="one"))["decision"] == "block"


def test_stop_loop_guard_does_not_block_twice():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = os.path.join(root, "code.py")
        _edit(path, "value = 1\n", "# Phase A\nvalue = 1\n", state)
        assert _stop(state, active=True) == ""


def test_subagent_stop_registration_contains_both_quality_gates():
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
    print(f"OK comment hooks — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
