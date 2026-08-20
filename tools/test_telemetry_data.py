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
        "instances": 1, "duplicate_starts": 0, "duplicate_stops": 0,
        "missing_start": 0, "missing_stop": 0,
        "unmatched": 0,
    }]
    assert report["hook_effectiveness"][0]["noted"] == 2
    assert report["recent_events"][0]["id"] == 4
    assert "/private/project" not in json.dumps(report)


def test_hook_invocations_are_reported_as_a_bounded_denominator():
    db = fresh_db()
    base = {"session_id": "s", "hook_event_name": "PostToolUse"}
    assert _hooklib.log_event(
        "hook_invocation",
        {"hook": "check.py", "hook_event": "PostToolUse"}, base,
    ) == "written"
    assert _hooklib.log_hook_signal(
        "check.py", "quality", "noted", 1, base, context="note"
    ) == "written"
    report = telemetry_data.build_report(db)
    row = report["hook_effectiveness"][0]
    assert row["invocations"] == 1
    assert row["denominator_from"]
    assert report["hook_invocations"][0]["hook"] == "check.py"


def test_hook_effectiveness_does_not_mix_old_signals_with_new_denominator():
    db = fresh_db()
    with sqlite3.connect(db) as connection:
        connection.execute(
            "INSERT INTO events(ts,schema_version,session_id,origin,event,payload) "
            "VALUES(?,?,?,?,?,?)",
            ("2026-08-19T09:00:00Z", 2, "old", "runtime", "hook_signal", json.dumps({
                "hook": "check.py", "rule_id": "quality", "outcome": "noted",
                "count": 3, "context_chars": 30,
            })),
        )
        connection.execute(
            "INSERT INTO events(ts,schema_version,session_id,origin,event,payload) "
            "VALUES(?,?,?,?,?,?)",
            ("2026-08-19T10:00:00Z", 2, "new", "runtime", "hook_invocation", json.dumps({
                "hook": "check.py", "hook_event": "PostToolUse",
            })),
        )
        connection.execute(
            "INSERT INTO events(ts,schema_version,session_id,origin,event,payload) "
            "VALUES(?,?,?,?,?,?)",
            ("2026-08-19T10:01:00Z", 2, "new", "runtime", "hook_signal", json.dumps({
                "hook": "check.py", "rule_id": "quality", "outcome": "noted",
                "count": 2, "context_chars": 20,
            })),
        )
    report = telemetry_data.build_report(db)
    row = report["hook_effectiveness"][0]
    assert row["signals"] == 1 and row["noted"] == 2 and row["sessions"] == 1
    assert row["context_chars"] == 20 and row["invocations"] == 1
    assert row["historical_before_denominator"] == {
        "signals": 1, "count": 3, "sessions": 1,
        "context_chars": 30, "last_seen": "2026-08-19T09:00:00Z",
    }
    assert report["harness_context_cost"]["characters"] == 50


def test_hook_resolution_links_only_to_earlier_same_session_signal():
    db = fresh_db()
    rows = (
        ("2026-08-19T10:00:00Z", "same", "noted", 2),
        ("2026-08-19T10:00:30Z", "other", "resolved", 1),
        ("2026-08-19T10:01:00Z", "same", "resolved", 3),
    )
    with sqlite3.connect(db) as connection:
        for timestamp, session_id, outcome, count in rows:
            connection.execute(
                "INSERT INTO events(ts,schema_version,session_id,origin,event,payload) "
                "VALUES(?,?,?,?,?,?)",
                (timestamp, 2, session_id, "runtime", "hook_signal", json.dumps({
                    "hook": "quality.py", "rule_id": "quality",
                    "outcome": outcome, "count": count, "context_chars": 0,
                })),
            )
    item = telemetry_data.build_report(db)["hook_effectiveness"][0]
    assert item["linked_resolutions"] == 2
    assert item["unlinked_resolutions"] == 2
    assert item["resolution_latency"] == {
        "samples": 2, "median_ms": 60_000, "p95_ms": 60_000,
        "max_ms": 60_000,
    }


def test_hook_resolution_does_not_invent_a_shared_missing_session():
    db = fresh_db()
    with sqlite3.connect(db) as connection:
        for timestamp, outcome in (
            ("2026-08-19T10:00:00Z", "noted"),
            ("2026-08-19T10:01:00Z", "resolved"),
        ):
            connection.execute(
                "INSERT INTO events(ts,schema_version,origin,event,payload) "
                "VALUES(?,?,?,?,?)",
                (timestamp, 2, "runtime", "hook_signal", json.dumps({
                    "hook": "quality.py", "rule_id": "quality",
                    "outcome": outcome, "count": 1, "context_chars": 0,
                })),
            )
    item = telemetry_data.build_report(db)["hook_effectiveness"][0]
    assert item["linked_resolutions"] == 0
    assert item["unlinked_resolutions"] == 1


def test_pending_telemetry_queue_remains_visible():
    db = fresh_db()
    pending = db.parent / "pending-events"
    pending.mkdir()
    (pending / "one.json").write_text("[]", encoding="utf-8")
    (pending / "two.json.claim-1").write_text("[]", encoding="utf-8")
    (pending / "three.json.claim-2.invalid").write_text("[]", encoding="utf-8")
    assert telemetry_data.build_report(db)["telemetry_queue"] == {
        "pending": 1, "claimed": 1, "invalid": 1,
    }


def test_session_concurrency_uses_only_paired_runtime_boundaries():
    db = fresh_db()
    rows = (
        ("2026-08-19T10:00:00Z", "first", "start"),
        ("2026-08-19T10:05:00Z", "second", "start"),
        ("2026-08-19T10:10:00Z", "first", "end"),
        ("2026-08-19T10:15:00Z", "second", "end"),
    )
    with sqlite3.connect(db) as connection:
        for timestamp, session_id, phase in rows:
            connection.execute(
                "INSERT INTO events(ts,schema_version,session_id,origin,event,payload) "
                "VALUES(?,?,?,?,?,?)",
                (timestamp, 2, session_id, "runtime", "session", json.dumps({
                    "phase": phase,
                    **({"source": "startup"} if phase == "start" else {
                        "end_reason": "other",
                    }),
                })),
            )

    concurrency = telemetry_data.build_report(db)["session_concurrency"]
    assert concurrency == {
        "evidence": "exact",
        "complete_runs": 2,
        "peak_active": 2,
        "overlap_sessions": 2,
        "overlap_ms": 5 * 60 * 1000,
        "missing_start": 0,
        "missing_end": 0,
        "duplicate_start": 0,
        "invalid_timestamp": 0,
    }


def test_session_concurrency_marks_unpaired_period_as_partial():
    db = fresh_db()
    with sqlite3.connect(db) as connection:
        connection.execute(
            "INSERT INTO events(ts,schema_version,session_id,origin,event,payload) "
            "VALUES(?,?,?,?,?,?)",
            ("2026-08-19T10:00:00Z", 2, "still-open", "runtime", "session",
             json.dumps({"phase": "start", "source": "startup"})),
        )
    concurrency = telemetry_data.build_report(db)["session_concurrency"]
    assert concurrency["evidence"] == "partial"
    assert concurrency["complete_runs"] == 0
    assert concurrency["missing_end"] == 1


def test_session_concurrency_restarts_after_missing_end_without_inventing_gap():
    summary = telemetry_data._session_concurrency_summary((
        ("2026-08-19T10:00:00Z", "resumed", "start"),
        ("2026-08-19T12:00:00Z", "resumed", "start"),
        ("2026-08-19T12:05:00Z", "resumed", "end"),
    ))
    assert summary["evidence"] == "partial"
    assert summary["duplicate_start"] == 1
    assert summary["complete_runs"] == 1
    assert summary["overlap_ms"] == 0


def test_pi_engineer_events_feed_shared_report_and_multi_adapter_view():
    db = fresh_db()
    run = {
        "sample_id": "pi-run", "mode": "new",
        "status": "ready-for-architect-review", "rounds": 2,
        "correction_rounds": 1, "checks_total": 2, "checks_passed": 2,
        "verifier_status": "ready-for-architect-review", "duration_ms": 1200,
        "tool_calls": 8, "repeated_tool_calls": 1, "failed_tool_calls": 0,
        "compactions": 1, "retries": 0, "executor_effort": "low",
        "verifier_effort": "high",
    }
    tool = {"sample_id": "pi-tool", "stage": "executor", "tool_name": "read", "calls": 3}
    with sqlite3.connect(db) as connection:
        for index, (event, payload) in enumerate((("engineer_run", run), ("engineer_tool_summary", tool)), 1):
            connection.execute(
                "INSERT INTO events(ts,schema_version,session_id,agent_type,project,model,origin,event,payload) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (f"2026-08-18T00:00:0{index}Z", 2, "hashed-session", "engineer", "hashed-project",
                 "provider/model", "runtime", event, json.dumps(payload)),
            )
    report = telemetry_data.build_report(db, adapter_id="pi")
    assert report["engineer_runs"]["runs"] == 1
    assert report["engineer_runs"]["ready"] == 1
    assert report["engineer_runs"]["correction_rounds"] == 1
    assert report["engineer_runs"]["checks_passed"] == 2
    assert report["engineer_tools"] == [{"stage": "executor", "tool_name": "read", "calls": 3}]
    combined = telemetry_data.build_multi_report({"pi": db})
    assert combined["engineer_runs"]["runs"] == 1
    assert combined["engineer_tools"][0]["adapter_id"] == "pi"


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


def test_period_filter_keeps_observation_bounds_and_filters_metrics():
    db = fresh_db()
    with sqlite3.connect(db) as connection:
        for timestamp, size in (
            ("2026-08-01T00:00:00Z", 1),
            ("2026-08-10T00:00:00Z", 2),
            ("2026-08-20T00:00:00Z", 3),
        ):
            connection.execute(
                "INSERT INTO events(ts,schema_version,session_id,agent_type,project,origin,event,payload) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (timestamp, 2, "s", "", "project", "runtime", "user_prompt",
                 json.dumps({"prompt_len": size})),
            )
    report = telemetry_data.build_report(
        db, start_timestamp="2026-08-05T00:00:00Z",
        end_timestamp="2026-08-15T00:00:00Z",
    )
    assert report["records"] == report["usable_records"] == 1
    assert report["stored_first_timestamp"] == "2026-08-01T00:00:00Z"
    assert report["stored_last_timestamp"] == "2026-08-20T00:00:00Z"
    assert report["first_timestamp"] == report["last_timestamp"] == "2026-08-10T00:00:00Z"


def test_workload_attributes_only_native_sessions_matching_subagent_ids():
    db = fresh_db()
    usage = {
        "sample_id": "sample", "source": "native-otel", "request_count": 2,
        "input_tokens": 100, "cached_input_tokens": 20,
        "cache_write_tokens": 0, "output_tokens": 30,
        "reasoning_output_tokens": 0, "total_tokens": 130,
    }
    with sqlite3.connect(db) as connection:
        connection.execute(
            "INSERT INTO events(ts,schema_version,session_id,agent_id,agent_type,project,origin,event,payload) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("2026-08-18T00:00:00Z", 2, "parent", "child", "reviewer", "project",
             "runtime", "subagent_start", "{}"),
        )
        connection.execute(
            "INSERT INTO events(ts,schema_version,session_id,agent_type,project,model,origin,event,payload) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("2026-08-18T00:00:01Z", 2, "child", "", "project", "model",
             "runtime", "model_usage", json.dumps(usage)),
        )
    report = telemetry_data.build_report(db, adapter_id="codex")
    assert report["workload"]["subagent_starts"] == 1
    assert report["workload"]["subagent_attributed_turns"] == 2
    assert report["workload"]["subagent_attributed_tokens"] == 130
    assert report["workload"]["by_subagent"][0]["processed_tokens"] == 130
    assert report["workload"]["by_subagent"][0]["agent"] == "reviewer"


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


def test_cli_adapter_summary_does_not_silently_return_all_adapters():
    db = fresh_db()
    assert _hooklib.log_event(
        "user_prompt", {"prompt_len": 4}, {"session_id": "s"}
    ) == "written"
    home = pathlib.Path(tempfile.mkdtemp())
    installed = home / ".claude/mainframe/claude-code/telemetry/telemetry.db"
    installed.parent.mkdir(parents=True)
    installed.write_bytes(pathlib.Path(db).read_bytes())
    result = subprocess.run(
        [sys.executable, str(TOOLS / "telemetry_data.py"),
         "--adapter", "claude-code"],
        check=True, capture_output=True, text=True,
        env={**os.environ, "HOME": str(home)},
    )
    report = json.loads(result.stdout)
    assert report["adapter_id"] == "claude-code"
    assert report["records"] == 1


def test_lifecycle_discrepancies_do_not_cancel_each_other():
    db = fresh_db()
    base = {"session_id": "s", "hook_event_name": "SubagentStart"}
    assert _hooklib.log_event(
        "subagent_start", {}, {**base, "agent_id": "a", "agent_type": "alpha"}
    ) == "written"
    for agent_id in ("b", "c"):
        assert _hooklib.log_event(
            "subagent_stop", {}, {
                **base, "hook_event_name": "SubagentStop",
                "agent_id": agent_id, "agent_type": "beta",
            },
        ) == "written"
    report = telemetry_data.build_report(db)
    lifecycle = {item["agent"]: item for item in report["agent_lifecycle"]}
    assert lifecycle["alpha"]["missing_stop"] == 1
    assert lifecycle["alpha"]["missing_start"] == 0
    assert lifecycle["beta"]["missing_start"] == 2
    assert lifecycle["beta"]["missing_stop"] == 0
    assert sum(item["unmatched"] for item in lifecycle.values()) == 3


def test_repeated_stop_for_the_same_agent_is_not_a_missing_start():
    db = fresh_db()
    agent = {"session_id": "s", "agent_id": "a", "agent_type": "reviewer"}
    assert _hooklib.log_event("subagent_start", {}, agent) == "written"
    assert _hooklib.log_event("subagent_stop", {}, agent) == "written"
    assert _hooklib.log_event("subagent_stop", {}, agent) == "written"
    lifecycle = telemetry_data.build_report(db)["agent_lifecycle"][0]
    assert lifecycle["instances"] == 1
    assert lifecycle["started"] == 1 and lifecycle["stopped"] == 2
    assert lifecycle["duplicate_stops"] == 1
    assert lifecycle["unmatched"] == 0


def test_multi_adapter_report_keeps_storage_and_evidence_separate():
    claude_db = fresh_db()
    assert _hooklib.log_event(
        "user_prompt", {"prompt_len": 4}, {"session_id": "claude"}
    ) == "written"

    codex_scripts = ROOT / "adapters" / "codex" / "hooks" / "scripts"
    sys.path.insert(0, str(codex_scripts))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mainframe_codex_telemetry_hooklib", codex_scripts / "_hooklib.py"
        )
        assert spec is not None and spec.loader is not None
        codex_hooklib = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(codex_hooklib)
        codex_db = pathlib.Path(tempfile.mkdtemp()) / "telemetry.db"
        os.environ["MAINFRAME_CODEX_TELEMETRY_DB"] = str(codex_db)
        os.environ["MAINFRAME_CODEX_TELEMETRY_ORIGIN"] = "runtime"
        codex_hooklib.initialize_telemetry_db(str(codex_db))
        assert codex_hooklib.log_event(
            "session", {"phase": "start", "source": "startup"},
            {
                "session_id": "codex", "hook_event_name": "SessionStart",
                "model": "gpt-test",
            },
        ) == "written"
    finally:
        sys.path.remove(str(codex_scripts))
        os.environ.pop("MAINFRAME_CODEX_TELEMETRY_DB", None)
        os.environ.pop("MAINFRAME_CODEX_TELEMETRY_ORIGIN", None)

    report = telemetry_data.build_multi_report({
        "claude-code": claude_db,
        "codex": codex_db,
    })
    assert report["active"] is True
    assert report["records"] == report["usable_records"] == 2
    assert [item["adapter_id"] for item in report["adapters"]] == [
        "claude-code", "codex",
    ]
    assert [item["records"] for item in report["adapters"]] == [1, 1]
    codex_report = next(
        item for item in report["adapters"] if item["adapter_id"] == "codex"
    )
    assert codex_report["by_model"] == [["gpt-test", 1]]
    assert {item["adapter_id"] for item in report["recent_events"]} == {
        "claude-code", "codex",
    }


def test_usage_costs_keep_exact_and_estimated_evidence_separate():
    db = fresh_db()
    base = {"session_id": "s", "prompt_id": "p", "model": "claude-test"}
    assert _hooklib.log_event(
        "model_usage",
        {
            "sample_id": "a" * 64,
            "source": "native-otel",
            "input_tokens": 1200,
            "cached_input_tokens": 800,
            "cache_write_tokens": 100,
            "output_tokens": 240,
            "reasoning_output_tokens": 0,
            "total_tokens": 1440,
            "request_count": 1,
        },
        base,
    ) == "written"
    assert _hooklib.log_hook_signal(
        "quality.py", "comment-quality", "noted", 1, base,
        context="x" * 120,
    ) == "written"

    report = telemetry_data.build_report(db)
    assert report["token_usage"] == {
        "evidence": "exact",
        "requests": 1,
        "input_tokens": 1200,
        "fresh_input_tokens": 1200,
        "cached_input_tokens": 800,
        "cache_write_tokens": 100,
        "request_context_tokens": 2100,
        "output_tokens": 240,
        "reasoning_output_tokens": 0,
        "total_tokens": 1440,
        "processed_tokens": 2340,
        "all_tokens": 2340,
        "by_source": [{
            "source": "native-otel",
            "requests": 1,
            "input_tokens": 1200,
            "fresh_input_tokens": 1200,
            "cached_input_tokens": 800,
            "cache_write_tokens": 100,
            "request_context_tokens": 2100,
            "output_tokens": 240,
            "reasoning_output_tokens": 0,
            "total_tokens": 1440,
            "processed_tokens": 2340,
            "all_tokens": 2340,
        }],
        "by_model": [{
            "model": "claude-test",
            "requests": 1,
            "input_tokens": 1200,
            "fresh_input_tokens": 1200,
            "cached_input_tokens": 800,
            "cache_write_tokens": 100,
            "request_context_tokens": 2100,
            "output_tokens": 240,
            "reasoning_output_tokens": 0,
            "total_tokens": 1440,
            "processed_tokens": 2340,
            "all_tokens": 2340,
        }],
    }
    assert report["harness_context_cost"] == {
        "evidence": "estimated",
        "characters": 120,
        "estimated_tokens_low": 20,
        "estimated_tokens_high": 60,
        "method": "character-range-2-to-6",
        "causal_overhead": "unproven",
    }
    assert "tokens_saved" not in report["harness_context_cost"]


def test_usage_contract_rejects_content_and_negative_counts():
    db = fresh_db()
    assert _hooklib.log_event(
        "model_usage",
        {
            "sample_id": "b" * 64,
            "source": "native-otel",
            "input_tokens": 1,
            "cached_input_tokens": 0,
            "cache_write_tokens": 0,
            "output_tokens": 1,
            "reasoning_output_tokens": 0,
            "total_tokens": 2,
            "request_count": 1,
            "prompt": "must not enter telemetry",
        },
        {"session_id": "s"},
    ) == "error"
    assert _hooklib.log_event(
        "model_usage",
        {
            "sample_id": "c" * 64,
            "source": "native-otel",
            "input_tokens": -1,
            "cached_input_tokens": 0,
            "cache_write_tokens": 0,
            "output_tokens": 1,
            "reasoning_output_tokens": 0,
            "total_tokens": 0,
            "request_count": 1,
        },
        {"session_id": "s"},
    ) == "error"
    assert telemetry_data.build_report(db)["records"] == 0


def _usage_row(sample, **overrides):
    payload = {
        "sample_id": sample, "source": "native-otel",
        "input_tokens": 100, "cached_input_tokens": 900, "cache_write_tokens": 10,
        "output_tokens": 50, "reasoning_output_tokens": 0, "total_tokens": 150,
        "request_count": 1,
    }
    payload.update(overrides)
    return payload


def test_claude_normalizes_separate_cache_counters_into_request_context():
    db = fresh_db()
    base = {"session_id": "s", "model": "claude-test"}
    assert _hooklib.log_event("model_usage", _usage_row("a" * 64), base) == "written"
    usage = telemetry_data.build_report(db)["token_usage"]
    assert usage["fresh_input_tokens"] == 100
    assert usage["request_context_tokens"] == 100 + 900 + 10
    assert usage["total_tokens"] == 150
    assert usage["processed_tokens"] == 100 + 900 + 10 + 50
    assert usage["all_tokens"] == 100 + 900 + 10 + 50


def test_codex_cached_input_is_a_subset_and_is_not_counted_twice():
    db = fresh_db()
    base = {"session_id": "s", "model": "codex-test"}
    row = _usage_row("a" * 64, input_tokens=1000, total_tokens=1050)
    assert _hooklib.log_event("model_usage", row, base) == "written"
    usage = telemetry_data.build_report(db, adapter_id="codex")["token_usage"]
    assert usage["fresh_input_tokens"] == 100
    assert usage["request_context_tokens"] == 1000
    assert usage["processed_tokens"] == 1050
    assert usage["all_tokens"] == 1050


def test_cost_evidence_tracks_how_many_requests_reported_a_price():
    db = fresh_db()
    base = {"session_id": "s", "model": "claude-test"}
    assert _hooklib.log_event("model_usage", _usage_row("a" * 64), base) == "written"
    report = telemetry_data.build_report(db)
    assert report["cost"]["evidence"] == "unavailable"
    assert report["cost"]["micro_usd"] == 0

    assert _hooklib.log_event(
        "model_usage", _usage_row("b" * 64, cost_micro_usd=2500), base) == "written"
    report = telemetry_data.build_report(db)
    # One of two requests priced: reporting it as a complete bill would overstate
    # coverage, so the evidence flag says partial and both counts are exposed.
    assert report["cost"]["evidence"] == "partial"
    assert report["cost"]["micro_usd"] == 2500
    assert report["cost"]["reporting_requests"] == 1
    assert report["cost"]["total_requests"] == 2

    db = fresh_db()
    assert _hooklib.log_event(
        "model_usage", _usage_row("c" * 64, cost_micro_usd=100), base) == "written"
    assert telemetry_data.build_report(db)["cost"]["evidence"] == "exact"


def test_latency_percentiles_come_from_reported_durations_only():
    db = fresh_db()
    base = {"session_id": "s", "model": "claude-test"}
    for index, duration in enumerate([10, 20, 30, 40, 1000]):
        assert _hooklib.log_event(
            "model_usage",
            _usage_row(str(index) * 64, duration_ms=duration), base) == "written"
    assert _hooklib.log_event("model_usage", _usage_row("z" * 64), base) == "written"
    latency = telemetry_data.build_report(db)["latency"]
    assert latency["samples"] == 5, "a row without a duration must not count as 0 ms"
    assert latency["median_ms"] == 30
    assert latency["p95_ms"] == 1000
    assert latency["max_ms"] == 1000


def test_tool_and_hook_signals_become_reliability_summaries():
    db = fresh_db()
    base = {"session_id": "s"}
    for index, success in enumerate([True, True, False]):
        assert _hooklib.log_event("tool_result", {
            "sample_id": f"t{index}", "tool_name": "Bash",
            "success": success, "duration_ms": 10 * (index + 1),
        }, base) == "written"
    assert _hooklib.log_event("tool_decision", {
        "sample_id": "d1", "tool_name": "Bash", "decision": "accept",
        "source": "config",
    }, base) == "written"
    assert _hooklib.log_event("hook_execution", {
        "sample_id": "h1", "hook_event": "PreToolUse", "hooks": 9, "succeeded": 8,
        "blocking": 1, "errors": 2, "cancelled": 0, "duration_ms": 72,
    }, base) == "written"

    report = telemetry_data.build_report(db)
    tools = report["tool_reliability"]
    assert tools == [{
        "tool_name": "Bash", "calls": 3, "failures": 1, "output_bytes": 0,
        "samples": 3, "median_ms": 20, "p95_ms": 30, "max_ms": 30,
    }]
    assert report["tool_decisions"] == [{
        "tool_name": "Bash", "decision": "accept", "source": "config", "count": 1,
    }]
    assert report["hook_health"] == [{
        "hook_event": "PreToolUse", "runs": 9, "errors": 2, "blocking": 1,
        "cancelled": 0, "samples": 1, "median_ms": 72, "p95_ms": 72, "max_ms": 72,
    }]


def test_uncounted_rows_name_their_reason():
    db = fresh_db()
    base = {"session_id": "s"}
    assert _hooklib.log_event("user_prompt", {"prompt_len": 5}, base) == "written"
    connection = sqlite3.connect(db)
    with connection:
        connection.execute(
            "INSERT INTO events(ts, schema_version, session_id, project, origin, "
            "event, payload) VALUES(?,?,?,?,?,?,?)",
            ("2026-01-01T00:00:00Z", 1, "s", "p", "runtime", "user_prompt", "{}"))
        connection.execute(
            "INSERT INTO events(ts, schema_version, session_id, project, origin, "
            "event, payload) VALUES(?,?,?,?,?,?,?)",
            ("2026-01-01T00:00:00Z", 2, "s", "p", "runtime", "not_an_event", "{}"))
        connection.execute(
            "INSERT INTO events(ts, schema_version, session_id, project, origin, "
            "event, payload) VALUES(?,?,?,?,?,?,?)",
            ("2026-01-01T00:00:00Z", 2, "s", "p", "synthetic", "user_prompt",
             json.dumps({"prompt_len": 1})))
    connection.close()

    report = telemetry_data.build_report(db)
    # "Excluded" on its own reads as data loss; each reason has a different fix.
    assert report["exclusions"]["legacy_schema"] == 1
    assert report["exclusions"]["unknown_event"] == 1
    assert report["exclusions"]["other_origin"] == 1
    assert report["excluded_records"] == 3
    assert report["stored_first_timestamp"] and report["stored_last_timestamp"]


def test_lifecycle_ignores_rows_without_an_agent_identity():
    db = fresh_db()
    base = {"session_id": "s"}
    # Codex fires SubagentStop at the end of a root turn with no agent attached.
    assert _hooklib.log_event("subagent_stop", {}, base) == "written"
    agent = {**base, "agent_id": "a1", "agent_type": "researcher"}
    assert _hooklib.log_event("subagent_start", {}, agent) == "written"
    assert _hooklib.log_event("subagent_stop", {}, agent) == "written"

    report = telemetry_data.build_report(db)
    assert [item["agent"] for item in report["agent_lifecycle"]] == ["researcher"]
    assert report["agent_lifecycle"][0]["unmatched"] == 0
    # The row is still stored and still counted as an event; it is only excluded
    # from a summary it cannot honestly contribute to.
    assert dict(report["event_counts"])["subagent_stop"] == 2


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
