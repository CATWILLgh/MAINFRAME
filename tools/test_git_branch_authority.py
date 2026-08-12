#!/usr/bin/env python3
"""Contract tests for the Git branch authority hook."""

import importlib.util
import json
import os
import subprocess
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters/claude-code/plugin/hooks/scripts/git-branch-authority.py"
)
spec = importlib.util.spec_from_file_location("git_branch_authority", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _reason(command):
    return hook.branch_mutation_reason(command)


def test_read_only_branch_commands_stay_silent():
    for command in (
        "git branch", "git branch --show-current", "git branch --list",
        "git branch -a", "git branch -r -v", "git branch --contains HEAD",
        "git branch --merged main", "git branch --format='%(refname:short)'",
        "git -C repo branch --list feature/*",
    ):
        assert _reason(command) is None, command


def test_branch_mutations_require_confirmation():
    for command in (
        "git branch feature", "git branch feature main",
        "git branch --track feature origin/main", "git branch -d feature",
        "git branch -D feature", "git branch -m old new",
        "git branch --copy old new", "git branch -f feature HEAD~1",
        "git branch --set-upstream-to=origin/main feature",
        "git branch --unset-upstream feature",
        "git -C repo branch feature",
    ):
        assert "explicit authorization" in _reason(command), command


def test_compound_nested_and_wrapped_commands_are_checked():
    for command in (
        "git status && git branch feature",
        "FOO=bar command git branch feature",
        "env FOO=bar git branch feature",
        "env -u OLD git branch feature",
        "env -C repo git branch feature",
        "sh -c 'git branch feature'",
        "eval 'git branch feature'",
    ):
        assert _reason(command), command
    assert _reason('echo "git branch feature"') is None


def test_cli_returns_ask_only_for_mutation():
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git branch feature"},
    }
    proc = subprocess.run(
        [sys.executable, SCRIPT], input=json.dumps(payload), text=True,
        capture_output=True, timeout=30, check=True,
    )
    result = json.loads(proc.stdout)
    assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
    payload["tool_input"]["command"] = "git branch --show-current"
    proc = subprocess.run(
        [sys.executable, SCRIPT], input=json.dumps(payload), text=True,
        capture_output=True, timeout=30, check=True,
    )
    assert proc.stdout == ""


def main():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK git-branch-authority — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
