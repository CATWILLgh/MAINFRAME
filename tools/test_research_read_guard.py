#!/usr/bin/env python3
"""Contract tests for the mainframe-researcher private Read boundary."""

import json
import os
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parent.parent
GUARD = ROOT / "adapters" / "claude-code" / "agents" / "hooks" / "research-read-guard.py"


SESSION_ID = "session-123"
AGENT_ID = "agent-456"


def run_guard(home: pathlib.Path, file_path=None, payload=None, mode="guard-read"):
    if payload is None:
        payload = {
            "session_id": SESSION_ID,
            "agent_id": AGENT_ID,
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": str(file_path)},
        }
    tmpdir = home / "tmp"
    tmpdir.mkdir(exist_ok=True)
    env = dict(os.environ, HOME=str(home), TMPDIR=str(tmpdir))
    proc = subprocess.run(
        ["python3", str(GUARD), mode],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]


def fixture():
    home = pathlib.Path(tempfile.mkdtemp())
    root = home / ".claude" / "skills" / "mainframe" / "skills" / "research-method"
    references = root / "references"
    references.mkdir(parents=True)
    (root / "SKILL.md").write_text("method", encoding="utf-8")
    (references / "news.md").write_text("news", encoding="utf-8")
    outside = home / "project" / "secret.txt"
    outside.parent.mkdir()
    outside.write_text("outside", encoding="utf-8")
    return home, root, outside


def record_fetch(home: pathlib.Path, tool_use_id: str):
    payload = {
        "session_id": SESSION_ID,
        "agent_id": AGENT_ID,
        "hook_event_name": "PreToolUse",
        "tool_name": "WebFetch",
        "tool_use_id": tool_use_id,
        "tool_input": {"url": "https://example.com"},
    }
    return run_guard(home, payload=payload, mode="record-webfetch")


def search(home: pathlib.Path):
    payload = {
        "session_id": SESSION_ID,
        "agent_id": AGENT_ID,
        "hook_event_name": "PreToolUse",
        "tool_name": "WebSearch",
        "tool_use_id": "toolu_search",
        "tool_input": {"query": "example"},
    }
    return run_guard(home, payload=payload, mode="require-profile")


def context7(home: pathlib.Path, tool_name: str):
    payload = {
        "session_id": SESSION_ID,
        "agent_id": AGENT_ID,
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_use_id": "toolu_context7",
        "tool_input": {"query": "example"},
    }
    return run_guard(home, payload=payload, mode="require-profile")


def test_allows_skill_and_reference_files():
    home, root, _ = fixture()
    assert run_guard(home, root / "SKILL.md")["permissionDecision"] == "allow"
    assert run_guard(home, root / "references" / "news.md")["permissionDecision"] == "allow"


def test_denies_every_file_outside_skill_root():
    home, _, outside = fixture()
    result = run_guard(home, outside)
    assert result["permissionDecision"] == "deny"
    assert "only its research-method skill directory" in result["permissionDecisionReason"]


def test_denies_symlink_escape():
    home, root, outside = fixture()
    link = root / "references" / "escape.md"
    link.symlink_to(outside)
    assert run_guard(home, link)["permissionDecision"] == "deny"


def test_allows_only_recorded_webfetch_output_for_same_session():
    home, root, _ = fixture()
    output_dir = home / ".claude" / "projects" / "project" / SESSION_ID / "tool-results"
    output_dir.mkdir(parents=True)
    allowed = output_dir / "toolu_own.txt"
    denied = output_dir / "toolu_other.txt"
    allowed.write_text("full fetch", encoding="utf-8")
    denied.write_text("another result", encoding="utf-8")

    assert run_guard(home, root / "references" / "news.md")["permissionDecision"] == "allow"
    assert record_fetch(home, "toolu_own")["permissionDecision"] == "allow"
    assert run_guard(home, allowed)["permissionDecision"] == "allow"
    assert run_guard(home, denied)["permissionDecision"] == "deny"

    other_session = dict(
        session_id="session-other",
        agent_id=AGENT_ID,
        hook_event_name="PreToolUse",
        tool_name="Read",
        tool_input={"file_path": str(allowed)},
    )
    assert run_guard(home, payload=other_session)["permissionDecision"] == "deny"


def test_external_research_requires_a_domain_profile():
    home, root, _ = fixture()
    assert run_guard(home, root / "SKILL.md")["permissionDecision"] == "allow"
    denied_search = search(home)
    assert denied_search["permissionDecision"] == "deny"
    assert "every applicable research profile" in denied_search["permissionDecisionReason"]
    assert record_fetch(home, "toolu_before_profile")["permissionDecision"] == "deny"
    for tool_name in (
        "mcp__plugin_context7_context7__resolve-library-id",
        "mcp__plugin_context7_context7__query-docs",
    ):
        assert context7(home, tool_name)["permissionDecision"] == "deny"

    assert run_guard(home, root / "references" / "news.md")["permissionDecision"] == "allow"
    assert search(home)["permissionDecision"] == "allow"
    assert record_fetch(home, "toolu_after_profile")["permissionDecision"] == "allow"
    for tool_name in (
        "mcp__plugin_context7_context7__resolve-library-id",
        "mcp__plugin_context7_context7__query-docs",
    ):
        assert context7(home, tool_name)["permissionDecision"] == "allow"


def test_fails_closed_for_bad_payload_or_missing_path():
    home, _, _ = fixture()
    bad_payload = {
        "session_id": SESSION_ID,
        "agent_id": AGENT_ID,
        "tool_name": "Read",
        "tool_input": {},
    }
    assert run_guard(home, payload=bad_payload)["permissionDecision"] == "deny"
    missing = home / ".claude" / "skills" / "mainframe" / "skills" / "research-method" / "missing.md"
    assert run_guard(home, missing)["permissionDecision"] == "deny"


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
