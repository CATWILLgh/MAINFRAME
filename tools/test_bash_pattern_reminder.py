#!/usr/bin/env python3
"""Tests for the narrow ripgrep short-cluster reminder."""

import importlib.util
import io
import itertools
import json
import os
import sys
import tempfile

os.environ["MAINFRAME_TELEMETRY_DB"] = os.path.join(
    tempfile.mkdtemp(prefix="bpr-telemetry-"), "telemetry.db"
)
os.environ["MAINFRAME_NOTICE_STATE_DIR"] = tempfile.mkdtemp(prefix="bpr-notices-")
_sessions = itertools.count()

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters/claude-code/plugin/hooks/scripts/bash-pattern-reminder.py"
)
spec = importlib.util.spec_from_file_location("bash_pattern_reminder", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _drive(command, tool="Bash", session=None, agent=None):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"command": command},
        "session_id": session or f"t-{next(_sessions)}",
        "agent_id": agent,
    }
    output = io.StringIO()
    saved = sys.stdin, sys.stdout
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.stdout = output
        hook.main()
    finally:
        sys.stdin, sys.stdout = saved
    return output.getvalue()


def test_short_replace_options_fire():
    for command in (
        'rg -rln "pattern" src',
        'rg -irn "pattern" src',
        "rg -nr pattern src",
        "/opt/bin/rg -ur pattern src",
        "rg -r ln pattern src",
        "rg -r=ln pattern src",
    ):
        output = _drive(command)
        assert "short `-r` form" in output and "--replace" in output, command


def test_reminder_is_once_per_session_and_writer():
    command = "rg -rni pattern src"
    assert _drive(command, session="shared", agent="writer")
    assert _drive(command, session="shared", agent="writer") == ""
    assert _drive(command, session="shared", agent="other")
    assert _drive(command, session="other", agent="writer")


def test_separate_or_explicit_replacement_is_silent():
    for command in (
        "rg -n pattern src",
        "rg -l -n pattern src",
        "rg --replace=ln pattern src",
        "rg -- -rln",
    ):
        assert _drive(command) == "", command


def test_option_values_that_look_like_flags_are_silent():
    for command in (
        "rg -g -r pattern src",
        "rg --glob -r pattern src",
        "rg -e -r src",
        "rg --regexp -r src",
    ):
        assert _drive(command) == "", command


def test_only_actual_rg_commands_fire():
    for command in (
        "echo rg -rln pattern src",
        "printf '%s' 'rg -rln pattern src'",
        "echo 'example: rg -rln pattern src'",
        "other-command --text 'rg -rln pattern src'",
    ):
        assert _drive(command) == "", command


def test_shell_operators_and_quotes_are_parsed():
    assert _drive('echo "a|b" && rg -rln pattern src')
    assert _drive("echo safe | rg -irn pattern src")
    assert _drive("echo 'rg -rln pattern src' && rg -n pattern src") == ""


def test_wrappers_and_nested_shell_are_supported():
    for command in (
        "MODE=test command rg -rln pattern src",
        "time rg -irn pattern src",
        "sh -c 'rg -nr pattern src'",
        "eval 'rg -rln pattern src'",
    ):
        assert _drive(command), command


def test_removed_historical_patterns_are_silent():
    for command in (
        "rm -rf ./cache",
        "cat > /tmp/file",
        "echo text > /tmp/file",
        "chmod +x /tmp/tool",
        "npm install -g package",
        "uv tool install package",
        "pipx install package",
    ):
        assert _drive(command) == "", command


def test_non_bash_and_malformed_commands_are_silent():
    assert _drive("rg -rln pattern", tool="Read") == ""
    assert _drive("rg -rln 'unterminated") == ""


def test_rendered_option_list_and_option_length_are_bounded():
    commands = [f"rg -{letter}r pattern src" for letter in "abcdefghij"]
    commands.append("rg -" + "a" * 1000 + "r pattern src")
    output = _drive(" ; ".join(commands))
    note = json.loads(output)["hookSpecificOutput"]["additionalContext"]
    assert "…and " in note
    assert "a" * 100 not in note
    assert len(note) < 600


def main():
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK bash-pattern-reminder — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
