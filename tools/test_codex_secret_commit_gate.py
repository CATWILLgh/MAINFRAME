#!/usr/bin/env python3
"""Codex delivery contract and scope-safety tests for the secret commit gate."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

import test_secret_commit_gate as shared
import test_codex_hooks as hook_contract


SCRIPTS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "adapters", "codex", "hooks", "scripts",
)
SCRIPT = os.path.join(SCRIPTS, "_secret_commit.py")
sys.path.insert(0, SCRIPTS)


def _load_gate():
    spec = importlib.util.spec_from_file_location("codex_secret_commit_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


shared.SCRIPTS = SCRIPTS
shared.SCRIPT = SCRIPT
shared.gate = _load_gate()


SHARED_CONTRACT = (
    shared.test_scan_finds_added_tokens_but_not_removed_or_placeholder,
    shared.test_clean_staged_commit_defers,
    shared.test_staged_secret_is_denied_without_value_in_reason,
    shared.test_commit_all_scans_tracked_worktree_and_staged_new_files,
    shared.test_explicit_pathspec_and_only_scan_worktree_content,
    shared.test_include_scans_existing_index_and_named_worktree_paths,
    shared.test_initial_commit_without_head_is_scanned,
    shared.test_git_c_and_cd_chain_scan_the_actual_repository,
    shared.test_env_and_nested_shell_forms_are_scanned,
    shared.test_sops_and_git_crypt_markers_do_not_disable_scanning,
    shared.test_non_commit_text_and_git_outside_repo_defer,
    shared.test_unverifiable_commit_forms_fail_closed,
    shared.test_parallel_read_only_scans_do_not_interfere,
)


def test_codex_gate_matches_the_shared_commit_contract():
    for test in SHARED_CONTRACT:
        test()


def test_git_environment_scope_overrides_fail_closed():
    root = shared._repo()
    alternate_index = os.path.join(tempfile.mkdtemp(), "alternate.index")
    env = dict(os.environ, GIT_INDEX_FILE=alternate_index)
    subprocess.run(
        ["git", "read-tree", "HEAD"], cwd=root, env=env, check=True,
        capture_output=True, text=True, timeout=30,
    )
    shared._write(root, "alternate.env", f"TOKEN={shared._ghp()}\n")
    subprocess.run(
        ["git", "add", "alternate.env"], cwd=root, env=env, check=True,
        capture_output=True, text=True, timeout=30,
    )
    quoted_index = shlex.quote(alternate_index)
    cases = (
        f"GIT_INDEX_FILE={quoted_index} git commit -m secret",
        f"env GIT_INDEX_FILE={quoted_index} git commit -m secret",
        "env -u GIT_INDEX_FILE git commit -m secret",
    )
    for command in cases:
        result = shared._run_hook(command, root)
        assert shared._decision(result) == "deny", command
        reason = result["hookSpecificOutput"]["permissionDecisionReason"]
        assert "git_environment_override" in reason, command


def test_other_scope_changing_wrappers_fail_closed():
    root = shared._repo()
    cases = (
        f"env -C {shlex.quote(root)} git commit -m x",
        "env --ignore-environment git commit -m x",
        "git -c core.worktree=. commit -m x",
        "git --config-env=core.worktree=WORKTREE commit -m x",
        "git --bare commit -m x",
    )
    for command in cases:
        result = shared._run_hook(command, root)
        assert shared._decision(result) == "deny", command
        assert "could not verify" in (
            result["hookSpecificOutput"]["permissionDecisionReason"]
        ), command


def test_harmless_environment_assignments_remain_supported():
    root = shared._repo()
    shared._write(root, ".env", f"TOKEN={shared._ghp()}\n")
    shared._git(root, "add", ".env")
    for command in (
        "MODE=test git commit -m secret",
        "env MODE=test git commit -m secret",
        "env -u MODE git commit -m secret",
    ):
        assert shared._decision(shared._run_hook(command, root)) == "deny", command


def test_dispatcher_delivers_the_gate_without_exposing_the_value():
    root = shared._repo()
    token = shared._ghp()
    shared._write(root, ".env", f"TOKEN={token}\n")
    shared._git(root, "add", ".env")
    state = Path(tempfile.mkdtemp()) / "state"
    proc, result = hook_contract._run_hook(
        hook_contract._tool_payload(
            Path(root), event="PreToolUse", command="git commit -m secret",
        ),
        state,
    )
    assert proc.returncode == 0, proc.stderr
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    reason = result["hookSpecificOutput"]["permissionDecisionReason"]
    assert "github_pat" in reason and token not in reason


def main():
    tests = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK codex-secret-commit-gate — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
