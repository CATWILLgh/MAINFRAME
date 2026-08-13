#!/usr/bin/env python3
"""Contract tests for primary-session Git delivery and repository authority."""

import importlib.util
import json
import os
import subprocess
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters/claude-code/plugin/hooks/scripts/git-authority.py"
)
spec = importlib.util.spec_from_file_location("git_branch_authority", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _reason(command):
    return hook.branch_mutation_reason(command)


def _decision(command, agent_id=None):
    return hook.authority_decision(command, agent_id)


def test_read_only_branch_commands_stay_silent():
    for command in (
        "git branch", "git branch --show-current", "git branch --list",
        "git branch -a", "git branch -r -v", "git branch --contains HEAD",
        "git branch --merged main", "git branch --format='%(refname:short)'",
        "git branch --format '%(refname:short)'",
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
        "git branch --color=always feature", "git branch --verbose feature",
        "git branch --column feature", "git branch --format='%(refname:short)' feature",
        "git branch --sort=refname feature",
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
        "noglob git branch feature",
        "nohup git branch feature",
        "timeout 30 git branch feature",
        "timeout -k 5 30 git branch feature",
        "nice -n 5 git branch feature",
        "stdbuf -oL git branch feature",
        "xargs git branch feature",
        "echo `git branch feature`",
        "sh -c 'git branch feature'",
        "eval 'git branch feature'",
    ):
        assert _reason(command), command
    assert _reason('echo "git branch feature"') is None


def test_subagents_cannot_stage_or_commit():
    for command in (
        "git add file.py", "git add -A", "git commit -m change",
        "git -C repo add file.py", "git -C repo commit -m change",
        "MODE=test command git add file.py",
        "git status && git commit -m change",
        "sh -c 'git add file.py && git commit -m change'",
        "git rm old.py", "git mv old.py new.py",
        "eval 'git commit -m change'",
    ):
        decision, reason = _decision(command, "agent-123")
        assert decision == "deny", command
        assert "primary session" in reason, command


def test_primary_session_keeps_staging_and_commit_authority():
    for command in (
        "git add file.py", "git add -A", "git commit -m change",
        "git status && git commit -m change", "git rm old.py",
        "git mv old.py new.py",
    ):
        assert _decision(command, None) == (None, None), command


def test_subagent_read_only_git_and_non_git_commands_stay_silent():
    for command in (
        "git status", "git diff", "git log -1", "git branch --show-current",
        "git stash list", "git stash show", "git worktree list",
        "git rm --dry-run old.py", "git mv --dry-run old.py new.py",
        "echo git commit -m example", "printf ok",
    ):
        assert _decision(command, "agent-123") == (None, None), command


def test_repository_mutations_require_confirmation_in_all_supported_forms():
    for command in (
        "git push origin main", "git -C repo push origin main",
        "git checkout feature", "git switch feature", "git stash",
        "git stash push",
        "git stash pop", "git pull", "git merge feature", "git rebase main",
        "git reset HEAD~1", "git cherry-pick HEAD~1", "git revert HEAD",
        "git commit --amend --no-edit", "git restore file.py",
        "git worktree add ../feature", "git worktree remove ../feature",
        "git worktree prune", "git clean -fd", "git clean --force -d",
        "git clean -i",
        "git fetch origin main:refs/heads/local-main",
        "git fetch origin +main:refs/heads/local-main",
        "git fetch --update-head-ok origin main:main",
        "git fetch --refmap=refs/heads/*:refs/local/* origin",
        "git fetch --force origin",
        "command git -C repo restore file.py",
        "/usr/bin/git restore file.py",
        "sh -c 'git worktree add ../feature && git status'",
    ):
        decision, reason = _decision(command)
        assert decision == "ask", command
        assert "explicit authorization" in reason, command


def test_read_only_repository_inspection_stays_silent():
    for command in (
        "git status", "git diff", "git log -1", "git stash list",
        "git stash show stash@{0}", "git worktree list --porcelain",
        "git worktree prune --dry-run", "git worktree prune -n",
        "git clean -n", "git clean --dry-run", "git branch --list",
        "git fetch", "git fetch origin", "git fetch origin main",
        "git fetch --all", "git fetch --prune origin",
    ):
        assert _decision(command) == (None, None), command


def test_force_push_and_verification_bypasses_are_denied():
    for command in (
        "git push --force origin main", "git push -f origin main",
        "git push -uf origin main", "git push --force-with-lease origin main",
        "git push --force-if-includes origin main", "git push --mirror origin",
        "git push origin +main", "git -C repo push origin +main",
        "git commit --no-verify -m change", "git commit -n -m change",
        "git commit -an -m change", "git -C repo rebase --no-verify main",
        "git merge --no-verify feature", "timeout 30 git -C repo push --force origin main",
        "xargs git push --force",
        "echo `git push --force origin main`",
        "sh -c 'git push --force origin main'",
    ):
        decision, reason = _decision(command)
        assert decision == "deny", command
        assert reason, command


def test_option_values_do_not_look_like_safety_bypasses():
    for command in (
        "git commit -m=-n", "git commit -m -n", "git commit -F -n",
        "git commit -m --no-verify", "git commit --message --no-verify",
        "git log -- --no-verify",
        "git fetch --server-option a:b origin",
        "git clean -e -f -n",
    ):
        assert _decision(command) == (None, None), command
    decision, _ = _decision("git push -o -f origin main")
    assert decision == "ask"
    decision, _ = _decision("git push -o --force origin main")
    assert decision == "ask"


def test_unparseable_git_fails_to_confirmation_without_blocking_plain_shell():
    decision, reason = _decision("git push 'unterminated")
    assert decision == "ask"
    assert "could not be classified" in reason
    assert _decision("printf 'unterminated") == (None, None)


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


def test_cli_denies_subagent_commit_but_not_primary_commit():
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": "session",
        "agent_id": "agent-123",
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m change"},
    }
    proc = subprocess.run(
        [sys.executable, SCRIPT], input=json.dumps(payload), text=True,
        capture_output=True, timeout=30, check=True,
    )
    result = json.loads(proc.stdout)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    payload.pop("agent_id")
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
    print(f"OK git-authority — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
