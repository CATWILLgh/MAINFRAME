#!/usr/bin/env python3
"""Tests for the narrow standalone secret-read guard."""

import importlib.util
import io
import json
import os
import sys
import tempfile

os.environ["MAINFRAME_TELEMETRY_DB"] = os.path.join(
    tempfile.mkdtemp(prefix="secret-read-telemetry-"), "telemetry.db"
)

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters", "claude-code", "plugin", "hooks", "scripts",
    "secret-read-guard.py",
)
spec = importlib.util.spec_from_file_location("secret_read_guard", SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def _drive(command, tool="Bash"):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"command": command},
        "session_id": "test-session",
    }
    output = io.StringIO()
    saved = sys.stdin, sys.stdout
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.stdout = output
        guard.main()
    finally:
        sys.stdin, sys.stdout = saved
    return output.getvalue()


def test_standalone_reads_are_denied():
    for command in (
        "secret get API_TOKEN",
        "  secret   get   'API_TOKEN'  ",
        "command secret get API_TOKEN",
        "/usr/local/bin/secret get API_TOKEN",
    ):
        output = _drive(command)
        assert '"permissionDecision": "deny"' in output, command
        assert "would expose the credential" in output, command


def test_consuming_commands_are_not_intercepted():
    for command in (
        'curl -H "Authorization: $(secret get API_TOKEN)" https://example.invalid',
        "secret get API_TOKEN | wc -c",
        "TOKEN=$(secret get API_TOKEN) consumer",
        "secret list",
        "secret get",
    ):
        assert _drive(command) == "", command


def test_non_bash_tools_are_ignored():
    assert _drive("secret get API_TOKEN", tool="Write") == ""


if __name__ == "__main__":
    failures = 0
    for name, value in sorted(globals().items()):
        if not name.startswith("test_") or not callable(value):
            continue
        try:
            value()
            print(f"  ok  {name}")
        except Exception as error:
            failures += 1
            print(f"FAIL  {name}: {error}")
    raise SystemExit(1 if failures else 0)
