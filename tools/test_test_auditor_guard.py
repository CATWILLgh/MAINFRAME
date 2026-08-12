#!/usr/bin/env python3
"""Tests for the test-auditor ticket-only write boundary."""

import json
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parent.parent
GUARD = ROOT / "adapters" / "claude-code" / "agents" / "hooks" / "test-auditor-write-guard.py"


def run_guard(root: pathlib.Path, tool: str, file_path: str):
    payload = {
        "session_id": "session",
        "agent_id": "agent",
        "cwd": str(root),
        "tool_name": tool,
        "tool_input": {"file_path": file_path},
    }
    proc = subprocess.run(
        ["python3", str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
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


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
