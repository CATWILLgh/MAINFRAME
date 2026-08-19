#!/usr/bin/env python3
"""Codex-owned development telemetry contract tests."""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "adapters" / "codex" / "hooks" / "scripts"


def _module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hooklib = _module("mainframe_codex_telemetry_test_hooklib", "_hooklib.py")


def _db() -> Path:
    return Path(tempfile.mkdtemp()) / "telemetry.db"


def test_explicit_sink_writes_allowlisted_metadata_only():
    db = _db()
    os.environ["MAINFRAME_CODEX_TELEMETRY_DB"] = str(db)
    try:
        result = hooklib.log_event(
            "user_prompt", {"prompt_len": 17}, {
                "session_id": "s", "turn_id": "t", "model": "gpt-test",
                "cwd": "/private/customer/project", "prompt": "do not retain",
                "hook_event_name": "UserPromptSubmit",
            },
        )
    finally:
        os.environ.pop("MAINFRAME_CODEX_TELEMETRY_DB", None)
    assert result == "written"
    with sqlite3.connect(db) as connection:
        row = connection.execute(
            "SELECT session_id, turn_id, model, project, event, payload FROM events"
        ).fetchone()
    assert row is not None and row[0:3] == ("s", "t", "gpt-test")
    serialized = json.dumps(row)
    assert "/private/customer/project" not in serialized
    assert "do not retain" not in serialized


def test_permission_request_is_separate_sensitive_local_data():
    db = _db()
    os.environ["MAINFRAME_CODEX_TELEMETRY_DB"] = str(db)
    try:
        result = hooklib.record_permission_request({
            "session_id": "permission-session", "permission_mode": "default",
            "tool_name": "Bash", "tool_input": {"command": "ssh internal-host"},
            "cwd": "/private/customer/project",
        })
    finally:
        os.environ.pop("MAINFRAME_CODEX_TELEMETRY_DB", None)
    assert result == "written"
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchone() is None
        row = connection.execute(
            "SELECT tool_input, permission_mode, decision, rule_evidence "
            "FROM permission_audit"
        ).fetchone()
    assert json.loads(row[0]) == {"command": "ssh internal-host"}
    assert row[1:] == ("default", None, "unavailable")


def test_default_sink_is_silent_without_dev_install():
    old = os.environ.pop("MAINFRAME_CODEX_TELEMETRY_DB", None)
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = tempfile.mkdtemp()
    try:
        assert hooklib.log_event(
            "user_prompt", {"prompt_len": 1}, {"session_id": "s"}
        ) == "disabled"
    finally:
        if old is not None:
            os.environ["MAINFRAME_CODEX_TELEMETRY_DB"] = old
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home


def test_parallel_writers_do_not_corrupt_database():
    db = _db()
    os.environ["MAINFRAME_CODEX_TELEMETRY_DB"] = str(db)
    hooklib.initialize_telemetry_db(str(db))
    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(
                lambda index: hooklib.log_event(
                    "user_prompt", {"prompt_len": index},
                    {"session_id": f"s-{index}", "turn_id": f"t-{index}"},
                ),
                range(80),
            ))
    finally:
        os.environ.pop("MAINFRAME_CODEX_TELEMETRY_DB", None)
    assert set(results) == {"written"}
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM events").fetchone()[0] == 80
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
