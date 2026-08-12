#!/usr/bin/env python3
"""Tests for session-scoped Fallow edit capture and audit-note rendering."""

import importlib.util
import json
import os
import sys
import tempfile
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(
    ROOT, "adapters", "claude-code", "plugin", "hooks", "scripts"
)
sys.path.insert(0, SCRIPTS)


def _module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


state = _module("fallow_state", "_fallow_state.py")
hook = _module("fallow_note", "fallow-quality-note.py")


def _workspace():
    root = tempfile.mkdtemp()
    state_root = os.path.join(root, "state")
    os.environ["MAINFRAME_FALLOW_STATE_DIR"] = state_root
    return root


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _payload(root, path, session="session-a", agent=None, tool="Write", **tool_input):
    value = {
        "cwd": root,
        "session_id": session,
        "agent_id": agent,
        "tool_name": tool,
        "tool_input": {"file_path": path},
    }
    value["tool_input"].update(tool_input)
    return value


def _audit_report(**overrides):
    report = {
        "kind": "audit",
        "verdict": "warn",
        "dead_code": {
            "unused_files": [
                {"path": "/repo/src/new.ts", "introduced": True},
                {"path": "/repo/src/old.ts", "introduced": False},
            ],
            "circular_dependencies": [{
                "files": ["src/a.ts", "src/b.ts"], "line": 3,
                "introduced": True,
            }],
            "boundary_violations": [{
                "from_path": "src/ui.ts", "to_path": "src/db.ts", "line": 7,
                "introduced": True,
            }],
            "boundary_call_violations": [],
            "unused_exports": [{"path": "src/noisy.ts", "introduced": True}],
        },
        "complexity": {"findings": [{
            "path": "src/service.ts", "line": 10, "name": "run",
            "cyclomatic": 22, "introduced": True,
        }]},
        "duplication": {"clone_groups": [{
            "instances": [{"file": "src/copy.ts", "start_line": 4}],
            "line_count": 18, "introduced": True,
        }]},
    }
    report.update(overrides)
    return report


def test_state_isolated_by_session_and_main_includes_subagents():
    root = _workspace()
    main = os.path.join(root, "main.ts")
    child = os.path.join(root, "child.ts")
    foreign = os.path.join(root, "foreign.ts")
    for path in (main, child, foreign):
        _write(path, f"export const {os.path.basename(path).split('.')[0]} = 1;\n")
    state.record(_payload(root, main))
    state.record(_payload(root, child, agent="agent-1"))
    state.record(_payload(root, foreign, session="session-b"))
    diff = state.build_diff("session-a", root, include_subagents=True)
    assert "main.ts" in diff and "child.ts" in diff
    assert "foreign.ts" not in diff


def test_ambiguous_repeated_edit_is_not_claimed():
    root = _workspace()
    path = os.path.join(root, "repeat.ts")
    _write(path, "same();\nsame();\n")
    state.record(_payload(
        root, path, tool="Edit", old_string="old();", new_string="same();"
    ))
    assert state.build_diff("session-a", root) == ""


def test_owned_line_survives_an_unrelated_line_shift():
    root = _workspace()
    path = os.path.join(root, "shift.ts")
    _write(path, "const owned = 2;\n")
    state.record(_payload(
        root, path, tool="Edit", old_string="const owned = 1;",
        new_string="const owned = 2;",
    ))
    _write(path, "const foreign = 0;\nconst owned = 2;\n")
    diff = state.build_diff("session-a", root)
    assert "@@ -0,0 +2,1 @@" in diff
    assert "+const owned = 2;" in diff
    assert "foreign" not in diff


def test_write_owns_the_current_file_but_not_another_file():
    root = _workspace()
    path = os.path.join(root, "written.ts")
    other = os.path.join(root, "other.ts")
    _write(path, "export const one = 1;\nexport const two = 2;\n")
    _write(other, "export const old = true;\n")
    state.record(_payload(root, path))
    diff = state.build_diff("session-a", root)
    assert "+export const one" in diff and "+export const two" in diff
    assert "other.ts" not in diff


def test_parallel_records_do_not_lose_files_or_persist_source_text():
    root = _workspace()
    payloads = []
    for index in range(24):
        path = os.path.join(root, "parallel", f"file-{index}.ts")
        _write(path, f"export const private_value_{index} = {index};\n")
        payloads.append(_payload(root, path))
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(state.record, payloads))
    diff = state.build_diff("session-a", root)
    assert all(f"file-{index}.ts" in diff for index in range(24))
    state_files = [
        os.path.join(os.environ["MAINFRAME_FALLOW_STATE_DIR"], name)
        for name in os.listdir(os.environ["MAINFRAME_FALLOW_STATE_DIR"])
        if name.endswith(".json")
    ]
    persisted = "".join(open(path, encoding="utf-8").read() for path in state_files)
    assert "private_value" not in persisted


def test_deletion_keeps_file_scope_without_storing_deleted_source():
    root = _workspace()
    path = os.path.join(root, "delete.ts")
    _write(path, "export const keep = true;\n")
    state.record(_payload(
        root, path, tool="Edit", old_string="secret_deleted_source();",
        new_string="",
    ))
    diff = state.build_diff("session-a", root)
    assert "delete.ts" in diff and "mainframe-session-deletion" in diff
    assert "secret_deleted_source" not in diff


def test_clear_prevents_repeat_analysis():
    root = _workspace()
    path = os.path.join(root, "once.ts")
    _write(path, "export const once = true;\n")
    state.record(_payload(root, path))
    assert state.build_diff("session-a", root)
    state.clear("session-a", include_subagents=True)
    assert state.build_diff("session-a", root) == ""


def test_note_reports_only_introduced_conservative_categories():
    note, counts = hook.build_note(
        _audit_report(), "/repo", {"/repo/src/new.ts"}
    )
    assert "new.ts" in note and "old.ts" not in note
    assert "noisy.ts" not in note
    assert "import cycle" in note and "boundary" in note
    assert "complexity" in note and "duplication" in note
    assert "inherited project debt" in note and "advisory" in note
    assert counts == {
        "unused_files": 1, "cycles": 1, "boundaries": 1,
        "complexity": 1, "duplication": 1,
    }


def test_note_is_silent_for_inherited_only_report():
    report = _audit_report(
        dead_code={"unused_files": [{"path": "old.ts", "introduced": False}]},
        complexity={"findings": [{"path": "old.ts", "introduced": False}]},
        duplication={"clone_groups": [{"introduced": False}]},
    )
    note, counts = hook.build_note(report)
    assert note is None and not any(counts.values())


def test_note_output_is_bounded():
    report = _audit_report(
        dead_code={
            "unused_files": [
                {"path": f"src/{index}.ts", "introduced": True}
                for index in range(20)
            ]
        },
        complexity={}, duplication={},
    )
    note, _ = hook.build_note(
        report, ".", {os.path.realpath(f"src/{index}.ts") for index in range(20)}
    )
    assert note.count("\n  - ") == hook.MAX_ROWS
    assert "…and 14 more" in note


def test_file_scoped_unused_finding_requires_whole_file_ownership():
    note, counts = hook.build_note(_audit_report(), "/repo", set())
    assert "unused file" not in note and counts["unused_files"] == 0


def test_audit_invocation_uses_head_session_diff_and_new_only_gate():
    original_which = hook.shutil.which
    original_run = hook.subprocess.run
    captured = {}
    try:
        hook.shutil.which = lambda name: "/fake/fallow" if name == "fallow" else None

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured.update(kwargs)
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"kind": "audit", "verdict": "pass"}),
                stderr="",
            )

        hook.subprocess.run = fake_run
        result = hook._run_audit("/repo", "session diff")
    finally:
        hook.shutil.which = original_which
        hook.subprocess.run = original_run
    assert result["kind"] == "audit"
    assert captured["command"] == [
        "/fake/fallow", "audit", "--root", "/repo", "--base", "HEAD",
        "--diff-stdin", "--gate", "new-only", "--format", "json", "--quiet",
    ]
    assert captured["input"] == "session diff"


def test_missing_fallow_is_a_reportable_failure():
    original = hook.shutil.which
    try:
        hook.shutil.which = lambda _name: None
        try:
            hook._installed_fallow()
        except RuntimeError as exc:
            assert "missing" in str(exc)
        else:
            raise AssertionError("missing Fallow must fail into the common reporter")
    finally:
        hook.shutil.which = original


def main():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK fallow delta hook — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
