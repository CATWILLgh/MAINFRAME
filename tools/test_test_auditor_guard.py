#!/usr/bin/env python3
"""Tests for the test-auditor ticket-only write boundary."""

import json
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parent.parent
GUARD = ROOT / "adapters" / "claude-code" / "agents" / "hooks" / "test-auditor-write-guard.py"


def run_guard(root: pathlib.Path, tool: str, file_path: str, mode: str = "write"):
    payload = {
        "session_id": "session",
        "agent_id": "agent",
        "cwd": str(root),
        "tool_name": tool,
        "tool_input": {"file_path": file_path},
    }
    args = ["python3", str(GUARD)]
    if mode != "write":
        args.append(mode)
    proc = subprocess.run(
        args,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


def run_bash_guard(root: pathlib.Path, command: str):
    payload = {
        "session_id": "session",
        "agent_id": "agent",
        "cwd": str(root),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    proc = subprocess.run(
        ["python3", str(GUARD), "ticket-move"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    if not proc.stdout:
        return None
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


def make_repo() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp())
    (root / ".git").mkdir()
    (root / "docs" / "tickets" / "open" / "needs-scope-review").mkdir(parents=True)
    (root / "docs" / "tickets" / "archive" / "resolved").mkdir(parents=True)
    return root


def test_allows_open_ticket_writes():
    root = make_repo()
    target = root / "docs" / "tickets" / "open" / "needs-scope-review" / "abcd-gap.md"
    assert run_guard(root, "Write", str(target)) == "allow"
    assert run_guard(root, "Edit", "docs/tickets/open/needs-scope-review/abcd-gap.md") == "allow"


def test_denies_product_and_archive_writes():
    root = make_repo()
    assert run_guard(root, "Write", "src/app.ts") == "deny"
    assert run_guard(root, "Edit", "tests/app.test.ts") == "deny"
    assert run_guard(root, "Write", "docs/tickets/archive/resolved/abcd-gap.md") == "deny"


def test_denies_path_escape_and_invalid_payload():
    root = make_repo()
    assert run_guard(root, "Write", "docs/tickets/open/../../outside.md") == "deny"
    assert run_guard(root, "Read", "docs/tickets/open/needs-scope-review/abcd-gap.md") == "deny"


def test_denies_symlink_escape():
    root = make_repo()
    outside = root / "outside"
    outside.mkdir()
    link = root / "docs" / "tickets" / "open" / "escape"
    link.symlink_to(outside, target_is_directory=True)
    assert run_guard(root, "Write", str(link / "abcd-gap.md")) == "deny"


def test_allows_only_open_ticket_moves_through_bash():
    root = make_repo()
    source = root / "docs" / "tickets" / "open" / "needs-scope-review" / "abcd-gap.md"
    source.write_text("ticket", encoding="utf-8")
    destination = root / "docs" / "tickets" / "open" / "ready" / "abcd-gap.md"
    destination.parent.mkdir()
    assert run_bash_guard(root, f"mv {source} {destination}") == "allow"
    assert run_bash_guard(root, f"mv {source} {root / 'outside.md'}") == "deny"
    assert run_bash_guard(root, f"mv {source} {destination} && echo moved") == "deny"
    assert run_bash_guard(root, "python3 -m pytest tests/unit") is None


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
