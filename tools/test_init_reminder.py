#!/usr/bin/env python3
"""Unit tests for the main-session-only init reminder hook."""

import importlib.util
import io
import json
import os
import sys
import tempfile

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters", "claude-code", "plugin", "hooks", "scripts",
    "init-reminder.py",
)
spec = importlib.util.spec_from_file_location("init_reminder", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _drive(payload, state_dir):
    out = io.StringIO()
    logged = []
    saved = sys.stdin, sys.stdout, hook._STATE_DIR, hook.log_event
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.stdout = out
        hook._STATE_DIR = state_dir
        hook.log_event = lambda *args, **kwargs: logged.append((args, kwargs))
        hook.main()
    finally:
        sys.stdin, sys.stdout, hook._STATE_DIR, hook.log_event = saved
    return out.getvalue(), logged


def _activate(state_dir, session_id="main"):
    return _drive({
        "hook_event_name": "UserPromptExpansion",
        "session_id": session_id,
        "expansion_type": "slash_command",
        "command_name": "mainframe:init",
        "command_source": "plugin",
    }, state_dir)


def _submit(state_dir, session_id="main", **extra):
    return _drive({
        "hook_event_name": "UserPromptSubmit",
        "session_id": session_id,
        "prompt": "continue",
        **extra,
    }, state_dir)


def test_inactive_session_is_silent():
    with tempfile.TemporaryDirectory() as state_dir:
        out, logged = _submit(state_dir)
        assert out == ""
        assert logged == []


def test_exact_manual_plugin_command_activates():
    with tempfile.TemporaryDirectory() as state_dir:
        out, logged = _activate(state_dir)
        assert out == ""
        assert logged and logged[0][0][0] == "init_reminder_activated"
        assert hook._load(hook._state_path("main", state_dir)) == (True, 0)


def test_other_expansion_does_not_activate():
    with tempfile.TemporaryDirectory() as state_dir:
        payload = {
            "hook_event_name": "UserPromptExpansion",
            "session_id": "main",
            "expansion_type": "slash_command",
            "command_name": "other:init",
            "command_source": "plugin",
        }
        _drive(payload, state_dir)
        assert hook._load(hook._state_path("main", state_dir)) == (False, 0)


def test_fires_on_64th_main_prompt_only():
    with tempfile.TemporaryDirectory() as state_dir:
        _activate(state_dir)
        for turn in range(1, 64):
            out, _ = _submit(state_dir)
            assert out == "", f"unexpected reminder on turn {turn}"
        out, logged = _submit(state_dir)
        result = json.loads(out)
        assert result["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert result["hookSpecificOutput"]["additionalContext"] == hook.INIT_NOTE
        assert logged[-1][0][1]["turn"] == 64
        assert logged[-1][0][1]["reminded"] is True


def test_subagent_cannot_activate_or_create_state():
    with tempfile.TemporaryDirectory() as state_dir:
        payload = {
            "hook_event_name": "UserPromptExpansion",
            "session_id": "sub",
            "agent_id": "agent-123",
            "expansion_type": "slash_command",
            "command_name": "mainframe:init",
            "command_source": "plugin",
        }
        out, logged = _drive(payload, state_dir)
        assert out == ""
        assert logged == []
        assert not os.path.exists(hook._state_path("sub", state_dir))


def test_subagent_neither_advances_nor_receives_reminder():
    with tempfile.TemporaryDirectory() as state_dir:
        _activate(state_dir)
        path = hook._state_path("main", state_dir)
        hook._save(path, True, 63)
        out, logged = _submit(
            state_dir, agent_id="agent-123", agent_type="researcher")
        assert out == ""
        assert logged == []
        assert hook._load(path) == (True, 63)


def test_main_agent_type_is_not_mistaken_for_subagent():
    with tempfile.TemporaryDirectory() as state_dir:
        _activate(state_dir)
        path = hook._state_path("main", state_dir)
        hook._save(path, True, 63)
        out, _ = _submit(state_dir, agent_type="primary-profile")
        assert out.strip()
        assert hook._load(path) == (True, 64)


def test_unrelated_event_does_not_advance():
    with tempfile.TemporaryDirectory() as state_dir:
        _activate(state_dir)
        path = hook._state_path("main", state_dir)
        hook._save(path, True, 63)
        out, logged = _drive({
            "hook_event_name": "Stop",
            "session_id": "main",
            "stop_hook_active": False,
        }, state_dir)
        assert out == ""
        assert logged == []
        assert hook._load(path) == (True, 63)


def test_session_lifecycle_preserves_only_the_intended_state():
    with tempfile.TemporaryDirectory() as state_dir:
        _activate(state_dir)
        for _ in range(10):
            _submit(state_dir)
        path = hook._state_path("main", state_dir)

        _drive({"hook_event_name": "SessionStart", "session_id": "main",
                "source": "resume"}, state_dir)
        assert hook._load(path) == (True, 10)

        _drive({"hook_event_name": "SessionStart", "session_id": "main",
                "source": "compact"}, state_dir)
        assert hook._load(path) == (True, 0)

        _drive({"hook_event_name": "SessionStart", "session_id": "main",
                "source": "clear"}, state_dir)
        assert hook._load(path) == (False, 0)


def test_state_is_per_session():
    with tempfile.TemporaryDirectory() as state_dir:
        _activate(state_dir, "one")
        _submit(state_dir, "one")
        assert hook._load(hook._state_path("one", state_dir)) == (True, 1)
        assert hook._load(hook._state_path("two", state_dir)) == (False, 0)


def test_missing_session_and_garbage_are_silent():
    with tempfile.TemporaryDirectory() as state_dir:
        out, logged = _drive({"hook_event_name": "Stop"}, state_dir)
        assert out == "" and logged == []

        saved = sys.stdin, sys.stdout, hook._STATE_DIR
        capture = io.StringIO()
        try:
            sys.stdin = io.StringIO("not-json")
            sys.stdout = capture
            hook._STATE_DIR = state_dir
            hook.main()
        finally:
            sys.stdin, sys.stdout, hook._STATE_DIR = saved
        assert capture.getvalue() == ""


def test_env_can_retune_positive_interval():
    saved = os.environ.get("MAINFRAME_INIT_REMINDER_EVERY")
    try:
        os.environ["MAINFRAME_INIT_REMINDER_EVERY"] = "3"
        assert hook._every() == 3
        os.environ["MAINFRAME_INIT_REMINDER_EVERY"] = "bad"
        assert hook._every() == 64
    finally:
        if saved is None:
            os.environ.pop("MAINFRAME_INIT_REMINDER_EVERY", None)
        else:
            os.environ["MAINFRAME_INIT_REMINDER_EVERY"] = saved


def main():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK init-reminder — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
