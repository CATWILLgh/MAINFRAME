#!/usr/bin/env python3
"""Unit and real-Git tests for the secret commit gate."""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "adapters/claude-code/plugin/hooks/scripts")
SCRIPT = os.path.join(SCRIPTS, "secret-commit-gate.py")
sys.path.insert(0, SCRIPTS)


def _load_gate():
    spec = importlib.util.spec_from_file_location("secret_commit_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load_gate()
ALNUM = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
UPPER = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _body(charset, size):
    return (charset * ((size // len(charset)) + 1))[:size]


def _ghp():
    return "ghp_" + _body(ALNUM, 36)


def _aws():
    return "AKIA" + _body(UPPER, 16)


def _diff(filename, added, removed=()):
    lines = [f"diff --git a/{filename} b/{filename}", f"--- a/{filename}",
             f"+++ b/{filename}", "@@ -1 +1 @@"]
    lines.extend(f"-{line}" for line in removed)
    lines.extend(f"+{line}" for line in added)
    return "\n".join(lines) + "\n"


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True, timeout=30)


def _repo(initial=True):
    root = tempfile.mkdtemp()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    if initial:
        with open(os.path.join(root, "base.txt"), "w", encoding="utf-8") as handle:
            handle.write("base\n")
        _git(root, "add", "base.txt")
        _git(root, "commit", "-qm", "base")
    return root


def _write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _run_hook(command, cwd, extra_env=None):
    payload = json.dumps({
        "hook_event_name": "PreToolUse", "session_id": "secret-test",
        "tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command},
    })
    env = dict(os.environ, MAINFRAME_FEEDBACK_NUDGE="0")
    env.pop("MAINFRAME_TELEMETRY_DB", None)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run([sys.executable, SCRIPT], input=payload, text=True,
                          capture_output=True, env=env, timeout=30, check=True)
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def _decision(result):
    return result["hookSpecificOutput"]["permissionDecision"] if result else None


def test_scan_finds_added_tokens_but_not_removed_or_placeholder():
    findings = gate._scan_diff_text(_diff(
        ".env", [f"GH={_ghp()}", f"AWS={_aws()}", "AKIAIOSFODNN7EXAMPLE"],
        removed=[f"OLD={_ghp()}"]))
    assert {kind for kind, _ in findings} == {"github_pat", "aws_access_key"}
    assert all(name == ".env" for _, name in findings)


def test_clean_staged_commit_defers():
    root = _repo()
    _write(root, "clean.txt", "clean\n")
    _git(root, "add", "clean.txt")
    assert _run_hook("git commit -m clean", root) is None


def test_staged_secret_is_denied_without_value_in_reason():
    root = _repo()
    token = _ghp()
    _write(root, ".env", f"TOKEN={token}\n")
    _git(root, "add", ".env")
    result = _run_hook("git commit -m secret", root)
    assert _decision(result) == "deny"
    reason = result["hookSpecificOutput"]["permissionDecisionReason"]
    assert "github_pat" in reason and ".env" in reason and token not in reason


def test_commit_all_scans_tracked_worktree_and_staged_new_files():
    root = _repo()
    _write(root, "base.txt", f"TOKEN={_ghp()}\n")
    assert _decision(_run_hook("git commit -am update", root)) == "deny"
    _write(root, "base.txt", "clean\n")
    _write(root, "new.env", f"TOKEN={_ghp()}\n")
    _git(root, "add", "new.env")
    assert _decision(_run_hook("git commit --all -m update", root)) == "deny"


def test_explicit_pathspec_and_only_scan_worktree_content():
    for command in ("git commit target.txt -m update",
                    "git commit --only target.txt -m update"):
        root = _repo()
        _write(root, "target.txt", "clean\n")
        _git(root, "add", "target.txt")
        _git(root, "commit", "-qm", "target")
        _write(root, "target.txt", f"TOKEN={_ghp()}\n")
        assert _decision(_run_hook(command, root)) == "deny", command


def test_include_scans_existing_index_and_named_worktree_paths():
    root = _repo()
    _write(root, "named.txt", "clean\n")
    _git(root, "add", "named.txt")
    _git(root, "commit", "-qm", "named")
    _write(root, "staged.env", f"TOKEN={_ghp()}\n")
    _git(root, "add", "staged.env")
    _write(root, "named.txt", "changed\n")
    assert _decision(_run_hook("git commit --include named.txt -m update", root)) == "deny"


def test_initial_commit_without_head_is_scanned():
    root = _repo(initial=False)
    _write(root, ".env", f"TOKEN={_ghp()}\n")
    _git(root, "add", ".env")
    assert _decision(_run_hook("git commit -m initial", root)) == "deny"


def test_git_c_and_cd_chain_scan_the_actual_repository():
    parent = tempfile.mkdtemp()
    root = os.path.join(parent, "repo")
    os.mkdir(root)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    _write(root, ".env", f"TOKEN={_ghp()}\n")
    _git(root, "add", ".env")
    assert _decision(_run_hook("git -C repo commit -m initial", parent)) == "deny"
    assert _decision(_run_hook("cd repo && git commit -m initial", parent)) == "deny"


def test_env_and_nested_shell_forms_are_scanned():
    root = _repo()
    _write(root, ".env", f"TOKEN={_ghp()}\n")
    _git(root, "add", ".env")
    for command in (
        "env MODE=test git commit -m secret",
        "sh -c 'git commit -m secret'",
        "eval 'git commit -m secret'",
    ):
        assert _decision(_run_hook(command, root)) == "deny", command


def test_literal_heredoc_body_does_not_hide_or_invent_a_commit():
    root = _repo()
    _write(root, "clean.txt", "clean\n")
    _git(root, "add", "clean.txt")
    clean_command = (
        "python3 - <<'PY2'\nprint('safe')\nPY2\n"
        "git commit -m 'safe message'"
    )
    assert _run_hook(clean_command, root) is None

    _write(root, ".env", f"TOKEN={_ghp()}\n")
    _git(root, "add", ".env")
    assert _decision(_run_hook(clean_command, root)) == "deny"

    body_only = "cat <<'TEXT'\ngit commit -m not-executed\nTEXT\n"
    assert _run_hook(body_only, root) is None


def test_unterminated_heredoc_fails_closed():
    root = _repo()
    command = "cat <<'TEXT'\nunfinished\ngit commit -m ambiguous"
    result = _run_hook(command, root)
    assert _decision(result) == "deny"
    assert "could not verify" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_sops_and_git_crypt_markers_do_not_disable_scanning():
    root = _repo()
    _write(root, ".sops.yaml", "creation_rules: []\n")
    _write(root, ".gitattributes", "secret filter=git-crypt diff=git-crypt\n")
    _write(root, "plain.env", f"TOKEN={_ghp()}\n")
    _git(root, "add", ".sops.yaml", ".gitattributes", "plain.env")
    assert _decision(_run_hook("git commit -m secrets", root)) == "deny"


def test_non_commit_text_and_git_outside_repo_defer():
    outside = tempfile.mkdtemp()
    assert _run_hook("echo git commit -m example", outside) is None
    assert _run_hook("git status", outside) is None
    assert _run_hook("git commit -m impossible", outside) is None


def test_unverifiable_commit_forms_fail_closed():
    root = _repo()
    cases = (
        "git --git-dir=.git commit -m x",
        "git commit --pathspec-from-file=paths.txt -m x",
        "cd $TARGET && git commit -m x",
        "git commit -m 'unterminated",
        "xargs git commit -m x",
        "sudo git commit -m x",
    )
    for command in cases:
        result = _run_hook(command, root)
        assert _decision(result) == "deny", command
        assert "could not verify" in result["hookSpecificOutput"]["permissionDecisionReason"]


def test_telemetry_contains_no_filename_or_secret_value():
    root = _repo()
    token = _ghp()
    filename = "private-production-name.env"
    _write(root, filename, f"TOKEN={token}\n")
    _git(root, "add", filename)
    db = os.path.join(tempfile.mkdtemp(), "telemetry.db")
    result = _run_hook("git commit -m secret", root,
                       {"MAINFRAME_TELEMETRY_DB": db})
    assert _decision(result) == "deny"
    with sqlite3.connect(db) as connection:
        row = connection.execute(
            "SELECT payload FROM events WHERE event='hook_signal'").fetchone()
    body = json.loads(row[0])
    assert body == {
        "hook": "secret-commit-gate.py", "rule_id": "secret-material",
        "outcome": "blocked", "count": 1,
        "context_chars": len(
            result["hookSpecificOutput"]["permissionDecisionReason"]),
    }
    assert filename not in row[0] and token not in row[0]


def test_parallel_read_only_scans_do_not_interfere():
    root = _repo()
    _write(root, ".env", f"TOKEN={_ghp()}\n")
    _git(root, "add", ".env")
    procs = []
    payload = json.dumps({
        "hook_event_name": "PreToolUse", "session_id": "parallel",
        "tool_name": "Bash", "cwd": root,
        "tool_input": {"command": "git commit -m secret"},
    })
    env = dict(os.environ, MAINFRAME_FEEDBACK_NUDGE="0")
    env.pop("MAINFRAME_TELEMETRY_DB", None)
    for _ in range(24):
        procs.append(subprocess.Popen(
            [sys.executable, SCRIPT], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env))
    outputs = [proc.communicate(payload, timeout=30) for proc in procs]
    assert all(proc.returncode == 0 for proc in procs), outputs
    assert all(_decision(json.loads(stdout)) == "deny" for stdout, _ in outputs)


def main():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK secret-commit-gate — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
