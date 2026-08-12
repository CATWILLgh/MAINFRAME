#!/usr/bin/env python3
"""Contract tests for the recursive-rm path circuit breaker."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters/claude-code/plugin/hooks/scripts/path-validation.py")
LAUNCHER = os.path.join(os.path.dirname(SCRIPT), "run-hook.sh")
spec = importlib.util.spec_from_file_location("path_validation", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _reason(command, cwd, project):
    return hook.decision_reason(command, cwd, project)


def test_safe_child_defers_to_normal_permissions():
    with tempfile.TemporaryDirectory() as project:
        assert _reason("rm -rf node_modules", project, project) is None
        assert _reason("/bin/rm -R ./build", project, project) is None


def test_project_root_requires_confirmation():
    with tempfile.TemporaryDirectory() as project:
        assert "project root" in _reason("rm -rf .", project, project)
        assert "project root" in _reason(f"rm -rf {project}", project, project)


def test_parent_and_absolute_external_paths_require_confirmation():
    with tempfile.TemporaryDirectory() as project:
        assert "outside" in _reason("rm -rf ../sibling", project, project)
        assert "outside" in _reason("rm -rf /tmp/external", project, project)


def test_symlink_escape_requires_confirmation():
    with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as outside:
        os.symlink(outside, os.path.join(project, "escape"))
        assert "outside" in _reason("rm -rf escape", project, project)


def test_shell_expansion_is_never_guessed():
    with tempfile.TemporaryDirectory() as project:
        for command in (
            "rm -rf $TARGET", "rm -rf $(pick_target)",
            "rm -rf `pick_target`", "rm -rf {cache,/tmp/cache}",
            "rm -rf cache/*", "rm -rf <(generate)",
        ):
            assert "shell expansion" in _reason(command, project, project), command


def test_directory_change_before_rm_requires_confirmation():
    with tempfile.TemporaryDirectory() as project:
        assert "directory change" in _reason(
            "cd /tmp && rm -rf cache", project, project)


def test_quoted_operator_is_not_a_shell_separator():
    with tempfile.TemporaryDirectory() as project:
        assert _reason('echo "a|b" && rm -rf cache', project, project) is None


def test_nested_shell_and_dynamic_targets_require_confirmation():
    with tempfile.TemporaryDirectory() as project:
        assert _reason("sh -c 'rm -rf /tmp/x'", project, project)
        assert "dynamically" in _reason("xargs rm -rf", project, project)
        assert "dynamically" in _reason(
            "find cache -type d -exec rm -rf {} +", project, project)


def test_wrapped_rm_is_checked_but_echo_is_not():
    with tempfile.TemporaryDirectory() as project:
        assert "outside" in _reason("sudo rm -rf /tmp/x", project, project)
        assert "outside" in _reason("sudo -u root rm -rf /tmp/x", project, project)
        assert "outside" in _reason("timeout 5 rm -rf /tmp/x", project, project)
        assert _reason("sudo echo rm -rf /tmp/x", project, project) is None
        assert _reason("echo rm -rf /tmp/x", project, project) is None


def test_nonrecursive_and_end_of_options_are_ignored():
    with tempfile.TemporaryDirectory() as project:
        assert _reason("rm -f /tmp/x", project, project) is None
        assert _reason("rm -- -recursive", project, project) is None


def test_unparseable_recursive_rm_requires_confirmation():
    with tempfile.TemporaryDirectory() as project:
        assert "could not be parsed" in _reason("rm -rf 'unterminated", project, project)


def test_cli_output_never_allows():
    with tempfile.TemporaryDirectory() as project:
        payload = json.dumps({
            "hook_event_name": "PreToolUse", "tool_name": "Bash",
            "cwd": project, "tool_input": {"command": "rm -rf ."},
        })
        env = dict(os.environ, CLAUDE_PROJECT_DIR=project)
        proc = subprocess.run([sys.executable, SCRIPT], input=payload, text=True,
                              capture_output=True, env=env, timeout=30, check=True)
        result = json.loads(proc.stdout)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
        assert '"allow"' not in proc.stdout


def test_launcher_preserves_the_ask_decision():
    with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as tmp:
        payload = json.dumps({
            "hook_event_name": "PreToolUse", "session_id": "path-test",
            "tool_name": "Bash", "cwd": project,
            "tool_input": {"command": "rm -rf ."},
        })
        env = dict(os.environ, CLAUDE_PROJECT_DIR=project, TMPDIR=tmp)
        proc = subprocess.run(
            ["sh", LAUNCHER, "PreToolUse", SCRIPT], input=payload, text=True,
            capture_output=True, env=env, timeout=30, check=True)
        result = json.loads(proc.stdout)
        assert result["hookSpecificOutput"]["permissionDecision"] == "ask"


def main():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK path-validation — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
