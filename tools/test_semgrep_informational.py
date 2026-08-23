#!/usr/bin/env python3
"""Focused contract tests for the adapter-owned Semgrep informational hooks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
CLAUDE_SCRIPT = (
    ROOT
    / "adapters"
    / "claude-code"
    / "plugin"
    / "hooks"
    / "scripts"
    / "semgrep-informational.py"
)
CODEX_SCRIPT = (
    ROOT / "adapters" / "codex" / "hooks" / "scripts" / "semgrep-informational.py"
)
CLAUDE_RULES = CLAUDE_SCRIPT.parent.parent / "rules" / "semgrep-informational.yml"
CODEX_RULES = CODEX_SCRIPT.parent.parent / "rules" / "semgrep-informational.yml"


def _load(path: Path, name: str):
    script_dir = str(path.parent)
    sys.path.insert(0, script_dir)
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(script_dir)


def _payload(path: Path, *, tool_name="Write", tool_input=None):
    return {
        "session_id": "semgrep-test-session",
        "tool_use_id": "semgrep-test-tool",
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input
        or {
            "file_path": str(path),
            "content": path.read_text(encoding="utf-8"),
        },
        "cwd": str(path.parent),
    }


def test_adapter_rule_packs_remain_identical_and_have_rule_fixtures():
    assert CLAUDE_RULES.read_text(encoding="utf-8") == CODEX_RULES.read_text(
        encoding="utf-8"
    )
    for rules in (CLAUDE_RULES.parent, CODEX_RULES.parent):
        assert (rules / "semgrep-informational.js").is_file()


def test_real_semgrep_scan_reports_only_supported_curated_rules():
    if shutil.which("semgrep") is None:
        return
    tmp_path = Path(tempfile.mkdtemp())
    module = _load(CODEX_SCRIPT, "mainframe_test_semgrep_real")
    source = tmp_path / "unsafe.js"
    source.write_text(
        'const child_process = require("child_process");\n'
        'child_process.exec(`echo ${value}`);\n',
        encoding="utf-8",
    )
    rows, raw = module._run_semgrep({source: {2}})
    assert raw == 1
    assert [row["rule_id"] for row in rows] == [
        "mainframe.javascript.dynamic-child-process-exec"
    ]


def test_edit_filter_ignores_findings_outside_new_text():
    tmp_path = Path(tempfile.mkdtemp())
    module = _load(CODEX_SCRIPT, "mainframe_test_semgrep_edit")
    source = tmp_path / "sample.js"
    source.write_text("unsafe()\nnew_value = 1\n", encoding="utf-8")
    payload = _payload(
        source,
        tool_name="Edit",
        tool_input={
            "file_path": str(source),
            "old_string": "new_value = 0",
            "new_string": "new_value = 1",
        },
    )
    assert module._targets(payload) == {source.resolve(): {2}}


def test_python_edits_are_left_to_the_faster_ruff_hook():
    tmp_path = Path(tempfile.mkdtemp())
    module = _load(CODEX_SCRIPT, "mainframe_test_semgrep_python_skip")
    source = tmp_path / "sample.py"
    source.write_text(
        "import subprocess\nsubprocess.run(command, shell=True)\n",
        encoding="utf-8",
    )
    assert module._targets(_payload(source)) == {}


def test_apply_patch_filter_maps_only_added_lines():
    tmp_path = Path(tempfile.mkdtemp())
    module = _load(CODEX_SCRIPT, "mainframe_test_semgrep_patch")
    source = tmp_path / "sample.js"
    source.write_text("safe = True\nunsafe = True\n", encoding="utf-8")
    patch = """*** Begin Patch
*** Update File: sample.js
@@
-unsafe = False
+unsafe = True
*** End Patch"""
    payload = _payload(source, tool_name="apply_patch", tool_input={"patch": patch})
    assert module._targets(payload) == {source.resolve(): {2}}


def test_apply_patch_filter_skips_ambiguous_repeated_added_text():
    tmp_path = Path(tempfile.mkdtemp())
    module = _load(CODEX_SCRIPT, "mainframe_test_semgrep_ambiguous_patch")
    source = tmp_path / "sample.js"
    source.write_text("unsafe = True\nunsafe = True\n", encoding="utf-8")
    patch = """*** Begin Patch
*** Update File: sample.js
@@
-unsafe = False
+unsafe = True
*** End Patch"""
    payload = _payload(source, tool_name="apply_patch", tool_input={"patch": patch})
    assert module._targets(payload) == {}


def test_main_is_advisory_bounded_and_deduplicated():
    tmp_path = Path(tempfile.mkdtemp())
    module = _load(CODEX_SCRIPT, "mainframe_test_semgrep_main")
    source = tmp_path / "sample.js"
    source.write_text("dangerous()\n", encoding="utf-8")
    payload = _payload(source)
    row = {
        "path": source,
        "line": 1,
        "end": 1,
        "rule_id": "mainframe.javascript.synthetic",
        "message": "Synthetic high-confidence finding.",
    }
    with (
        mock.patch.object(module, "_run_semgrep", return_value=([row], 1)),
        mock.patch.object(module, "log_event", return_value="disabled"),
        mock.patch.object(module, "log_hook_signal", return_value="disabled"),
        mock.patch.dict(
            os.environ,
            {"MAINFRAME_NOTICE_STATE_DIR": str(tmp_path / "notices")},
        ),
    ):

        def invoke():
            original = sys.stdin
            output = io.StringIO()
            try:
                sys.stdin = io.StringIO(json.dumps(payload))
                with redirect_stdout(output):
                    module.main()
            finally:
                sys.stdin = original
            return output.getvalue()

        first = invoke()
        second = invoke()
    parsed = json.loads(first)
    note = parsed["hookSpecificOutput"]["additionalContext"]
    assert "Semgrep advice found 1" in note
    assert "advisory and is not a full project scan" in note
    assert "dangerous()" not in note
    assert second == ""


def test_runtime_failure_is_visible_once_without_failing_the_hook():
    tmp_path = Path(tempfile.mkdtemp())
    module = _load(CODEX_SCRIPT, "mainframe_test_semgrep_failure")
    source = tmp_path / "sample.js"
    source.write_text("value = 1\n", encoding="utf-8")
    payload = _payload(source)
    events = []
    with (
        mock.patch.object(
            module, "_run_semgrep", side_effect=RuntimeError("synthetic")
        ),
        mock.patch.object(
            module,
            "log_event",
            side_effect=lambda event, body, _payload: (
                events.append((event, body)) or "written"
            ),
        ),
        mock.patch.dict(
            os.environ,
            {"MAINFRAME_NOTICE_STATE_DIR": str(tmp_path / "notices")},
        ),
    ):
        original = sys.stdin
        output = io.StringIO()
        try:
            sys.stdin = io.StringIO(json.dumps(payload))
            with redirect_stdout(output):
                module.main()
        finally:
            sys.stdin = original

    parsed = json.loads(output.getvalue())
    assert (
        "advisory check was skipped"
        in (parsed["hookSpecificOutput"]["additionalContext"])
    )
    assert events[0][0] == "analyzer_run"
    assert events[0][1]["status"] == "failed"


def test_parallel_identical_findings_emit_one_bounded_notice():
    if shutil.which("semgrep") is None:
        return
    tmp_path = Path(tempfile.mkdtemp())
    source = tmp_path / "unsafe.js"
    source.write_text(
        'const child_process = require("child_process");\n'
        'child_process.exec(`echo ${value}`);\n',
        encoding="utf-8",
    )
    payload = json.dumps(_payload(source))
    environment = {
        **os.environ,
        "MAINFRAME_NOTICE_STATE_DIR": str(tmp_path / "notices"),
    }

    def invoke(_index):
        return subprocess.run(
            [sys.executable, "-B", str(CODEX_SCRIPT)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=20,
            env=environment,
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(invoke, range(6)))
    assert all(result.returncode == 0 for result in results)
    visible = [result.stdout for result in results if result.stdout.strip()]
    assert len(visible) == 1
    note = json.loads(visible[0])["hookSpecificOutput"]["additionalContext"]
    assert "Semgrep advice found 1" in note
    assert len(note) < 1200


def test_detailed_analyzer_telemetry_requires_each_adapters_dev_sink():
    tmp_path = Path(tempfile.mkdtemp())
    source = tmp_path / "unsafe.js"
    source.write_text(
        'const child_process = require("child_process");\n'
        'child_process.exec(`echo ${value}`);\n',
        encoding="utf-8",
    )
    payload = json.dumps(_payload(source))
    cases = (
        (
            CLAUDE_SCRIPT,
            "MAINFRAME_TELEMETRY_DB",
            tmp_path
            / "home"
            / ".claude"
            / "mainframe"
            / "claude-code"
            / "telemetry"
            / "telemetry.db",
        ),
        (
            CODEX_SCRIPT,
            "MAINFRAME_CODEX_TELEMETRY_DB",
            tmp_path
            / "home"
            / ".codex"
            / "mainframe"
            / "codex"
            / "telemetry"
            / "telemetry.db",
        ),
    )
    for index, (script, variable, ordinary_db) in enumerate(cases):
        environment = {
            **os.environ,
            "HOME": str(tmp_path / "home"),
            "MAINFRAME_NOTICE_STATE_DIR": str(tmp_path / f"notices-{index}"),
        }
        environment.pop("MAINFRAME_TELEMETRY_DB", None)
        environment.pop("MAINFRAME_CODEX_TELEMETRY_DB", None)
        ordinary = subprocess.run(
            [sys.executable, "-B", str(script)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=20,
            env=environment,
        )
        assert ordinary.returncode == 0
        assert not ordinary_db.exists()

        dev_db = tmp_path / f"dev-{index}" / "telemetry.db"
        environment[variable] = str(dev_db)
        environment["MAINFRAME_NOTICE_STATE_DIR"] = str(
            tmp_path / f"dev-notices-{index}"
        )
        development = subprocess.run(
            [sys.executable, "-B", str(script)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=20,
            env=environment,
        )
        assert development.returncode == 0
        with sqlite3.connect(dev_db) as connection:
            assert connection.execute(
                "SELECT count(*) FROM events WHERE event = 'analyzer_run'"
            ).fetchone() == (1,)


def test_both_adapter_scripts_share_the_reviewed_runtime_contract():
    assert CLAUDE_SCRIPT.read_text(encoding="utf-8") == CODEX_SCRIPT.read_text(
        encoding="utf-8"
    )


def test_both_telemetry_sinks_accept_native_semgrep_rule_ids():
    for script, database_variable in (
        (CLAUDE_SCRIPT, "MAINFRAME_TELEMETRY_DB"),
        (CODEX_SCRIPT, "MAINFRAME_CODEX_TELEMETRY_DB"),
    ):
        root = Path(tempfile.mkdtemp())
        database = root / "telemetry.db"
        environment = dict(os.environ)
        environment[database_variable] = str(database)
        command = (
            "import _hooklib; "
            "assert _hooklib.log_hook_signal("
            "'semgrep-informational.py', "
            "'mainframe.javascript.dynamic-child-process-exec', "
            "'noted', 1, {'session_id': 's'}, context='advice'"
            ") == 'written'"
        )
        completed = subprocess.run(
            [sys.executable, "-B", "-c", command],
            cwd=script.parent,
            capture_output=True,
            text=True,
            timeout=20,
            env=environment,
        )
        assert completed.returncode == 0, completed.stderr
        with sqlite3.connect(database) as connection:
            payload = json.loads(connection.execute(
                "SELECT payload FROM events WHERE event = 'hook_signal'"
            ).fetchone()[0])
        assert payload["rule_id"] == "mainframe.javascript.dynamic-child-process-exec"
        assert payload["context_chars"] == len("advice")


def main():
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK Semgrep informational hooks — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
