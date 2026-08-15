#!/usr/bin/env python3
"""Codex behavior tests for comment reminders and their Stop gate."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import test_codex_hooks as dispatcher_contract


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "adapters" / "codex" / "hooks" / "scripts"
REMINDER = SCRIPTS / "comment-discipline-reminder.py"
STOP = SCRIPTS / "stop-gate-comment-discipline.py"


def _env(state: Path) -> dict[str, str]:
    return dict(
        os.environ,
        MAINFRAME_MARKER_STATE_DIR=str(state / "markers"),
        MAINFRAME_NOTICE_STATE_DIR=str(state / "notices"),
    )


def _run(script: Path, payload: dict, state: Path) -> dict | None:
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_env(state),
        timeout=20,
        check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def _edit(
    path: Path,
    before: str,
    after: str,
    state: Path,
    *,
    session: str = "session",
    agent: str = "",
) -> dict | None:
    path.write_text(after, encoding="utf-8")
    return _run(REMINDER, {
        "hook_event_name": "PostToolUse",
        "session_id": session,
        "agent_id": agent,
        "tool_name": "Edit",
        "cwd": str(path.parent),
        "tool_input": {
            "file_path": str(path),
            "old_string": before,
            "new_string": after,
        },
    }, state)


def _stop(
    root: Path,
    state: Path,
    *,
    session: str = "session",
    agent: str = "",
) -> dict | None:
    return _run(STOP, {
        "hook_event_name": "SubagentStop" if agent else "Stop",
        "session_id": session,
        "agent_id": agent,
        "cwd": str(root),
        "stop_hook_active": False,
    }, state)


def _fake_token() -> str:
    return "ghp_" + "A" * 36


def test_targeted_output_identifies_location_without_repeating_source():
    root = Path(tempfile.mkdtemp())
    state = Path(tempfile.mkdtemp())
    path = root / "code.py"
    before = "value = 1\n"
    token = _fake_token()
    after = f"# Phase 2: {token}\n{before}"
    note = _edit(path, before, after, state)
    context = note["hookSpecificOutput"]["additionalContext"]
    assert "code.py:1 (comment)" in context
    assert token not in context and "Phase 2" not in context
    blocked = _stop(root, state)
    reason = blocked["reason"]
    assert "code.py:1 (comment)" in reason
    assert token not in reason and "Phase 2" not in reason


def test_durable_rewrite_resolves_the_owned_candidate():
    root = Path(tempfile.mkdtemp())
    state = Path(tempfile.mkdtemp())
    path = root / "code.py"
    before = "value = 1\n"
    transient = "# Step 1: retry\n" + before
    _edit(path, before, transient, state)
    durable = "# Retry once because duplicate requests are billable.\n" + before
    _edit(path, transient, durable, state)
    assert _stop(root, state) is None


def test_identical_candidates_in_two_files_are_counted_separately():
    root = Path(tempfile.mkdtemp())
    state = Path(tempfile.mkdtemp())
    for name in ("first.py", "second.py"):
        path = root / name
        _edit(path, "value = 1\n", "# Phase 2\nvalue = 1\n", state)
    blocked = _stop(root, state)
    assert blocked["reason"].startswith("2 unresolved comment candidates")
    assert "first.py:1" in blocked["reason"]
    assert "second.py:1" in blocked["reason"]


def test_preexisting_identical_candidate_is_not_counted_as_session_work():
    root = Path(tempfile.mkdtemp())
    state = Path(tempfile.mkdtemp())
    path = root / "code.py"
    before = "# Phase 2\nvalue = 1\n"
    after = "# Phase 2\n# Phase 2\nvalue = 1\n"
    _edit(path, before, after, state)
    blocked = _stop(root, state)
    assert blocked["reason"].startswith("1 unresolved comment candidate")
    assert "code.py (1 matching comment candidate)" in blocked["reason"]


def test_generic_reminder_is_once_per_session_and_agent():
    root = Path(tempfile.mkdtemp())
    state = Path(tempfile.mkdtemp())
    comment = "# Retry once because duplicate requests are billable.\nvalue = 1\n"
    first = _edit(root / "one.py", "value = 1\n", comment, state, agent="writer")
    assert "Every comment must preserve durable" in (
        first["hookSpecificOutput"]["additionalContext"]
    )
    assert _edit(
        root / "two.py", "value = 1\n", comment, state, agent="writer",
    ) is None
    assert _edit(
        root / "two.py", "value = 1\n", comment, state, agent="other",
    ) is not None


def test_parallel_generic_reminders_emit_once():
    root = Path(tempfile.mkdtemp())
    state = Path(tempfile.mkdtemp())
    comment = "# Retry once because duplicate requests are billable.\nvalue = 1\n"

    def invoke(index: int) -> dict | None:
        return _edit(
            root / f"file-{index}.py", "value = 1\n", comment, state,
            session="parallel", agent="writer",
        )

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(invoke, range(24)))
    assert sum(result is not None for result in results) == 1


def test_dispatcher_preserves_location_only_through_post_and_stop():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    path = root / "code.py"
    before = "value = 1\n"
    token = _fake_token()
    path.write_text(before, encoding="utf-8")
    pre = dispatcher_contract._patch_payload(
        root, path.name, event="PreToolUse", tool_use="comment",
    )
    proc, result = dispatcher_contract._run_hook(pre, state)
    assert proc.returncode == 0 and result is None

    path.write_text(f"# Phase 2: {token}\n{before}", encoding="utf-8")
    post = dispatcher_contract._patch_payload(
        root, path.name, event="PostToolUse", tool_use="comment",
    )
    proc, result = dispatcher_contract._run_hook(post, state)
    assert proc.returncode == 0
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "code.py:1 (comment)" in context
    assert token not in context and "Phase 2" not in context

    stop = {
        "session_id": "session",
        "turn_id": "turn",
        "agent_id": "",
        "hook_event_name": "Stop",
        "cwd": str(root),
        "stop_hook_active": False,
    }
    _, blocked = dispatcher_contract._run_hook(stop, state)
    assert "code.py:1 (comment)" in blocked["reason"]
    assert token not in blocked["reason"] and "Phase 2" not in blocked["reason"]


def main():
    tests = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK codex-comment-hooks — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
