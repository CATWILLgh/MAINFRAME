#!/usr/bin/env python3
"""Tests for the shared machine/UI telemetry reader."""

import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "adapters" / "claude-code" / "plugin" / "hooks" / "scripts"
TOOLS = ROOT / "tools"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TOOLS))

import _hooklib  # noqa: E402
import telemetry_data  # noqa: E402


def fresh_db():
    db = pathlib.Path(tempfile.mkdtemp()) / "telemetry.db"
    os.environ["MAINFRAME_TELEMETRY_DB"] = str(db)
    os.environ["MAINFRAME_TELEMETRY_ORIGIN"] = "runtime"
    _hooklib.initialize_telemetry_db(str(db))
    return db


def test_report_and_stream_share_the_same_rows():
    db = fresh_db()
    base = {"session_id": "s", "prompt_id": "p", "cwd": "/private/project"}
    assert _hooklib.log_event("user_prompt", {"prompt_len": 5}, base) == "written"
    agent = {**base, "agent_id": "a", "agent_type": "mainframe-researcher",
             "hook_event_name": "SubagentStart"}
    assert _hooklib.log_event("subagent_start", {}, agent) == "written"
    agent["hook_event_name"] = "SubagentStop"
    assert _hooklib.log_event("subagent_stop", {}, agent) == "written"
    assert _hooklib.log_hook_signal(
        "check.py", "quality", "noted", 2, base, context="short note"
    ) == "written"

    rows = list(telemetry_data.iter_events(db))
    report = telemetry_data.build_report(db)
    assert [row["id"] for row in rows] == [1, 2, 3, 4]
    assert report["records"] == len(rows) == 4
    assert report["usable_records"] == 4
    assert report["sessions"] == 1 and report["agent_instances"] == 1
    assert report["invalid_rows"] == 0 and report["legacy_rows"] == 0
    assert report["agent_lifecycle"] == [{
        "agent": "mainframe-researcher", "started": 1, "stopped": 1,
        "instances": 1, "unmatched": 0,
    }]
    assert report["hook_effectiveness"][0]["noted"] == 2
    assert report["recent_events"][0]["id"] == 4
    assert "/private/project" not in json.dumps(report)


def test_incremental_stream_uses_after_id_and_limit():
    db = fresh_db()
    for size in range(5):
        _hooklib.log_event("user_prompt", {"prompt_len": size}, {"session_id": "s"})
    rows = list(telemetry_data.iter_events(db, after_id=2, limit=2))
    assert [row["id"] for row in rows] == [3, 4]
    assert [row["data"]["prompt_len"] for row in rows] == [2, 3]


def test_report_keeps_independent_breakdown_dimensions():
    db = fresh_db()
    assert _hooklib.log_event(
        "skill_request", {"skill": "init", "invoker": "user"},
        {"session_id": "s", "hook_event_name": "UserPromptExpansion"},
    ) == "written"
    assert _hooklib.log_event(
        "skill_request", {"skill": "init", "invoker": "model"},
        {"session_id": "s", "tool_use_id": "t", "hook_event_name": "PreToolUse"},
    ) == "written"
    report = telemetry_data.build_report(db)
    breakdowns = {
        (item["event"], item["key"]): dict(item["items"])
        for item in report["breakdowns"]
    }
    assert breakdowns[("skill_request", "skill")] == {"init": 2}
    assert breakdowns[("skill_request", "invoker")] == {"user": 1, "model": 1}


def test_legacy_and_invalid_rows_are_visible_not_silently_counted_as_valid():
    db = pathlib.Path(tempfile.mkdtemp()) / "legacy.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, "
            "session_id TEXT, agent_type TEXT, project TEXT, event TEXT, payload TEXT)"
        )
        connection.executemany(
            "INSERT INTO events(ts, session_id, event, payload) VALUES (?,?,?,?)",
            [
                ("2026-01-01T00:00:00", "s", "old_event", "{}"),
                ("2026-01-01T00:00:01", "s", "skill_load", "not json"),
            ],
        )
    report = telemetry_data.build_report(db)
    assert report["legacy_rows"] == 2
    assert report["usable_records"] == 0
    assert report["invalid_rows"] == 1
    assert dict(report["unknown_events"])["old_event"] == 1
    assert report["invalid_examples"][0]["id"] == 2


def test_invalid_current_rows_do_not_contaminate_metrics():
    db = fresh_db()
    with sqlite3.connect(db) as connection:
        connection.execute(
            "INSERT INTO events(ts, schema_version, session_id, event, payload) "
            "VALUES (?,?,?,?,?)",
            ("2026-01-01T00:00:00.000Z", 2, "s", "user_prompt", '{"prompt_len":"bad"}'),
        )
    report = telemetry_data.build_report(db)
    assert report["records"] == 1 and report["invalid_rows"] == 1
    assert report["usable_records"] == 0
    assert report["sessions"] == 0 and report["event_counts"] == []
    assert report["recent_events"] == []


def test_missing_database_is_an_inactive_clean_state():
    report = telemetry_data.build_report("/definitely/missing/telemetry.db")
    assert report["active"] is False and report["records"] == 0
    assert report["error"] == ""


def test_old_uuid_sessions_are_inferred_without_rewriting_provenance():
    assert telemetry_data._effective_origin(
        "unclassified", "00893aaf-19fa-41d2-8238-13269b9b3ca0"
    ) == "runtime-inferred"
    assert telemetry_data._effective_origin("unclassified", "parallel") == "unclassified"
    assert telemetry_data._effective_origin(
        "synthetic", "00893aaf-19fa-41d2-8238-13269b9b3ca0"
    ) == "synthetic"


def test_report_can_isolate_runtime_from_model_lab_rows():
    db = fresh_db()
    assert _hooklib.log_event(
        "user_prompt", {"prompt_len": 5},
        {"session_id": "runtime", "_telemetry_origin": "runtime"},
    ) == "written"
    os.environ["MAINFRAME_TELEMETRY_ORIGIN"] = "model-lab"
    assert _hooklib.log_event(
        "model_lab",
        {
            "provider": "google-antigravity", "model": "gemini-3.7-flash-high",
            "effort": "high", "task": "telemetry-audit", "status": "completed",
            "elapsed_bucket_s": 10,
        },
        {"session_id": "lab", "_telemetry_origin": "model-lab"},
    ) == "written"
    os.environ["MAINFRAME_TELEMETRY_ORIGIN"] = "runtime"

    default = telemetry_data.build_report(db)
    runtime = telemetry_data.build_report(
        db, included_origins={"runtime", "runtime-inferred"}
    )
    assert default["usable_records"] == 2
    assert default["included_origins"] == ["model-lab", "runtime", "runtime-inferred"]
    assert runtime["records"] == 2 and runtime["usable_records"] == 1
    assert runtime["excluded_records"] == 1
    assert runtime["included_origins"] == ["runtime", "runtime-inferred"]
    assert dict(runtime["event_counts"]) == {"user_prompt": 1}


def test_cli_exposes_summary_and_incremental_jsonl():
    db = fresh_db()
    for size in (4, 8):
        assert _hooklib.log_event(
            "user_prompt", {"prompt_len": size}, {"session_id": "s"}
        ) == "written"
    script = TOOLS / "telemetry_data.py"
    summary = subprocess.run(
        [sys.executable, str(script), "--db", str(db)],
        check=True, capture_output=True, text=True,
    )
    report = json.loads(summary.stdout)
    assert report["records"] == 2 and report["last_id"] == 2

    stream = subprocess.run(
        [sys.executable, str(script), "--db", str(db), "--format", "jsonl",
         "--after-id", "1", "--limit", "1"],
        check=True, capture_output=True, text=True,
    )
    rows = [json.loads(line) for line in stream.stdout.splitlines()]
    assert len(rows) == 1 and rows[0]["id"] == 2
    assert rows[0]["data"] == {"prompt_len": 8}


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
