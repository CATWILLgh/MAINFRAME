#!/usr/bin/env python3
"""Behavior tests for the Codex ripgrep option reminder."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "adapters" / "codex" / "hooks" / "scripts"
SCRIPT = SCRIPTS / "_bash_patterns.py"
DISPATCHER = SCRIPTS / "mainframe-hook.py"
sys.path.insert(0, str(SCRIPTS))


def _load_module():
    spec = importlib.util.spec_from_file_location("codex_bash_patterns", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


patterns = _load_module()


def _payload(command: str, *, session: str = "session", agent: str = "") -> str:
    return json.dumps({
        "hook_event_name": "PreToolUse",
        "session_id": session,
        "agent_id": agent,
        "tool_name": "Bash",
        "cwd": str(ROOT),
        "tool_input": {"command": command},
    })


def _run(
    command: str,
    state: Path,
    *,
    session: str = "session",
    agent: str = "",
    dispatcher: bool = False,
) -> dict | None:
    env = dict(os.environ, MAINFRAME_NOTICE_STATE_DIR=str(state))
    result = subprocess.run(
        [sys.executable, str(DISPATCHER if dispatcher else SCRIPT)],
        input=_payload(command, session=session, agent=agent),
        text=True,
        capture_output=True,
        env=env,
        timeout=20,
        check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def test_detects_actual_short_replace_forms():
    cases = {
        "rg -r X needle .": ["-r"],
        "rg -rn needle .": ["-rn"],
        "rg -nr X needle .": ["-nr"],
        "rg needle . -or X": ["-or"],
        "/opt/local/bin/rg -irn needle .": ["-irn"],
        "bash -lc 'rg -rn needle .'": ["-rn"],
        "rg -n one . && rg -r=X two .": ["-r=X"],
    }
    for command, expected in cases.items():
        assert patterns.short_rg_replace_options(command) == expected, command


def test_ignores_explicit_replace_values_examples_and_other_option_values():
    commands = (
        "rg -n needle .",
        "rg needle . --replace X",
        "rg needle . --replace=X",
        "rg -trust needle .",
        "rg -g -r needle .",
        "rg -e -r .",
        "rg --glob -r needle .",
        "rg -- -r .",
        "echo 'rg -rn needle .'",
        "printf '%s\\n' 'rg -r X needle .'",
    )
    for command in commands:
        assert patterns.short_rg_replace_options(command) == [], command


def test_reminder_is_advisory_and_scoped_per_session_and_agent():
    state = Path(tempfile.mkdtemp()) / "notices"
    first = _run("rg -rn needle .", state)
    assert first["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in first["hookSpecificOutput"]
    context = first["hookSpecificOutput"]["additionalContext"]
    assert "--replace" in context and "not blocked" in context
    assert _run("rg -r X needle .", state) is None
    child = _run("rg -rn needle .", state, agent="child")
    assert child is not None
    other_session = _run("rg -rn needle .", state, session="other")
    assert other_session is not None


def test_parallel_repeats_emit_one_reminder():
    state = Path(tempfile.mkdtemp()) / "notices"

    def invoke(_index: int) -> dict | None:
        return _run("rg -rn needle .", state, session="parallel")

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(invoke, range(24)))
    assert sum(result is not None for result in results) == 1


def test_dispatcher_delivers_one_bounded_note():
    state = Path(tempfile.mkdtemp()) / "notices"
    result = _run("rg -rn needle .", state, dispatcher=True)
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "ripgrep option check" in context
    assert len(context) < 500


def test_blocked_command_does_not_consume_the_later_reminder():
    state = Path(tempfile.mkdtemp()) / "notices"
    blocked = _run(
        "rm -rf generated && rg -rn needle .", state, dispatcher=True,
    )
    assert blocked["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "ripgrep option check" not in (
        blocked["hookSpecificOutput"]["permissionDecisionReason"]
    )
    later = _run("rg -rn needle .", state, dispatcher=True)
    assert "ripgrep option check" in (
        later["hookSpecificOutput"]["additionalContext"]
    )


def main():
    tests = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK codex-bash-patterns — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
