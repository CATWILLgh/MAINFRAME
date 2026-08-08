#!/usr/bin/env python3
"""Unit tests for the secret-commit PreToolUse gate.

Run: `python3 tools/test_secret_commit_gate.py` (exit 0 = pass). Stdlib only,
Tier 1 — no real git: the diff-parsing layer is fed canned diff text, and the
main() orchestration is driven with the git-touching helpers monkeypatched.

Fixture tokens are ASSEMBLED AT RUNTIME from a charset (never a literal token in
source) so this very test file is safe to commit through the live gate — the
staged source never contains a secret-shaped string.
"""

import importlib.util
import io
import json
import os
import sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "adapters/claude-code/plugin", "hooks", "scripts")
sys.path.insert(0, _SCRIPTS)
import _hooklib


def _load_gate():
    path = os.path.join(_SCRIPTS, "secret-commit-gate.py")
    spec = importlib.util.spec_from_file_location("secret_commit_gate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load_gate()

_ALNUM = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_UPPER = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _body(charset, n):
    """Varied run-free body of length n — no 8+ identical run, no 'example'."""
    return (charset * ((n // len(charset)) + 1))[:n]


def _ghp():
    return "ghp_" + _body(_ALNUM, 36)


def _aws():
    return "AKIA" + _body(_UPPER, 16)


def _stripe():
    return "sk_live_" + _body(_ALNUM, 24)


def _diff(filename, added_lines, removed_lines=()):
    out = [f"diff --git a/{filename} b/{filename}",
           "index 1111111..2222222 100644",
           f"--- a/{filename}", f"+++ b/{filename}",
           "@@ -1,0 +1,9 @@"]
    out += [f"-{l}" for l in removed_lines]
    out += [f"+{l}" for l in added_lines]
    return "\n".join(out) + "\n"


def test_scan_finds_github_pat():
    tok = _ghp()
    hits = gate._scan_diff_text(_diff(".env", [f"GITHUB_TOKEN={tok}"]))
    assert any(k == "github_pat" for k, _ in hits), hits
    assert all(f == ".env" for _, f in hits)


def test_scan_finds_aws_and_stripe():
    text = _diff("config.yaml", [f"aws: {_aws()}", f"stripe: {_stripe()}"])
    kinds = {k for k, _ in gate._scan_diff_text(text)}
    assert "aws_access_key" in kinds and "stripe_key" in kinds, kinds


def test_aws_example_placeholder_ignored():
    # Real AWS doc example key — matches the regex but is a placeholder.
    text = _diff("README.md", ["key = AKIAIOSFODNN7EXAMPLE"])
    assert gate._scan_diff_text(text) == [], gate._scan_diff_text(text)


def test_removed_line_not_flagged():
    # A secret on a deleted (`-`) line is not newly entering history.
    text = _diff(".env", ["clean=1"], removed_lines=[f"OLD={_ghp()}"])
    assert not any(k == "github_pat" for k, _ in gate._scan_diff_text(text))


def test_is_placeholder_detects_repeats_and_keywords():
    assert gate._is_placeholder("ghp_" + "a" * 36)        # 8+ identical run
    assert gate._is_placeholder("AKIAIOSFODNN7EXAMPLE")   # keyword
    assert not gate._is_placeholder(_ghp())               # real-shaped


def test_commit_stages_all():
    assert gate._commit_stages_all("git commit -am 'x'")
    assert gate._commit_stages_all("git commit -a -m 'x'")
    assert gate._commit_stages_all("git commit --all -m 'x'")
    assert not gate._commit_stages_all("git commit -m 'x'")
    assert not gate._commit_stages_all("git commit --amend -m 'x'")


def test_is_git_commit_shared_helper():
    assert _hooklib.is_git_commit("git commit -m 'x'")
    assert _hooklib.is_git_commit("git -C /p commit -m 'x'")
    assert not _hooklib.is_git_commit("git status")


def _drive(command, *, repo="/repo", encrypted=False, findings=None,
           tool="Bash", session="s1", agent_type=""):
    """Run gate.main() against a payload, with git helpers stubbed. Returns the
    parsed stdout JSON (or None when the gate deferred with no output)."""
    gate._repo_root = lambda cwd: repo
    gate._is_encrypted_repo = lambda root: encrypted
    gate._scan_staged = lambda root, include_unstaged: list(findings or [])
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool,
               "session_id": session, "agent_type": agent_type, "cwd": "/repo",
               "tool_input": {"command": command}}
    old_in, old_out = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps(payload))
    sys.stdout = io.StringIO()
    try:
        gate.main()
        captured = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = old_in, old_out
    return json.loads(captured) if captured.strip() else None


def test_deny_on_secret():
    os.environ["MAINFRAME_FEEDBACK_NUDGE"] = "0"
    out = _drive("git commit -m 'x'", findings=[("github_pat", ".env")])
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert "github_pat" in reason and ".env" in reason


def test_deny_reason_omits_secret_value():
    os.environ["MAINFRAME_FEEDBACK_NUDGE"] = "0"
    tok = _ghp()
    # The gate is handed findings as (kind, file) only — it never receives the
    # value, so it cannot leak it. Assert the contract end to end.
    out = _drive("git commit -m 'x'", findings=[("github_pat", "secrets.env")])
    assert tok not in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_encrypted_repo_allows_silently():
    out = _drive("git commit -m 'x'", encrypted=True,
                 findings=[("github_pat", ".env")])
    assert out is None                       # defer: no decision emitted


def test_clean_commit_defers():
    out = _drive("git commit -m 'x'", findings=[])
    assert out is None


def test_non_commit_bash_defers():
    out = _drive("ls -la", findings=[("github_pat", ".env")])
    assert out is None


def test_non_bash_tool_defers():
    out = _drive("git commit -m 'x'", tool="Skill",
                 findings=[("github_pat", ".env")])
    assert out is None


def test_not_a_git_repo_defers():
    gate._repo_root = lambda cwd: None
    payload = {"tool_name": "Bash", "cwd": "/x",
               "tool_input": {"command": "git commit -m 'x'"}}
    old_in, old_out = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps(payload))
    sys.stdout = io.StringIO()
    try:
        gate.main()
        captured = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = old_in, old_out
    assert not captured.strip()


def test_telemetry_logged_on_block():
    import tempfile
    import sqlite3
    os.environ["MAINFRAME_FEEDBACK_NUDGE"] = "0"
    db = os.path.join(tempfile.mkdtemp(), "telemetry.db")
    os.environ["MAINFRAME_TELEMETRY_DB"] = db
    _drive("git commit -m 'x'", findings=[("aws_access_key", "prod.env")])
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT event, payload FROM events WHERE event='secret_block'").fetchall()
    finally:
        con.close()
    assert len(rows) == 1, rows
    body = json.loads(rows[0][1])
    assert "aws_access_key" in body["types"] and "prod.env" in body["files"]
    del os.environ["MAINFRAME_TELEMETRY_DB"]


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK secret-commit-gate — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
