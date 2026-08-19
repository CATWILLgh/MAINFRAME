#!/usr/bin/env python3
"""Tests for the local privacy-safe native OTLP usage receiver."""

import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import native_telemetry_receiver as receiver  # noqa: E402
import otlp_ingest_health  # noqa: E402
import telemetry_data  # noqa: E402


def _attribute(rows, key, value):
    item = rows.add()
    item.key = key
    if isinstance(value, int):
        item.value.int_value = value
    else:
        item.value.string_value = value


def _batch(adapter_id):
    from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
        ExportLogsServiceRequest,
    )

    request = ExportLogsServiceRequest()
    resource = request.resource_logs.add()
    _attribute(resource.resource.attributes, "service.name", adapter_id)
    record = resource.scope_logs.add().log_records.add()
    record.time_unix_nano = 123456
    if adapter_id == "claude-code":
        _attribute(record.attributes, "event.name", "claude_code.api_request")
        _attribute(record.attributes, "session.id", "claude-session")
        _attribute(record.attributes, "request_id", "request-1")
        _attribute(record.attributes, "model", "claude-test")
        _attribute(record.attributes, "input_tokens", 100)
        _attribute(record.attributes, "output_tokens", 20)
        _attribute(record.attributes, "cache_read_tokens", 60)
        _attribute(record.attributes, "cache_creation_tokens", 5)
        _attribute(record.attributes, "cost_usd_micros", 4200)
        _attribute(record.attributes, "duration_ms", 1500)
        _attribute(record.attributes, "prompt", "must never persist")
    else:
        _attribute(record.attributes, "event.name", "codex.sse_event")
        _attribute(record.attributes, "event.kind", "response.completed")
        _attribute(record.attributes, "conversation.id", "codex-session")
        _attribute(record.attributes, "model", "gpt-test")
        _attribute(record.attributes, "input_token_count", 200)
        _attribute(record.attributes, "output_token_count", 30)
        _attribute(record.attributes, "cached_token_count", 120)
        _attribute(record.attributes, "reasoning_token_count", 10)
        _attribute(record.attributes, "tool_token_count", 230)
        _attribute(record.attributes, "user.email", "private@example.com")
        _attribute(record.attributes, "output", "must never persist")
    return request


def test_protobuf_batches_keep_only_allowlisted_usage():
    samples = []
    for adapter_id in ("claude-code", "codex"):
        request = _batch(adapter_id)
        samples.extend(receiver.decode_logs(
            request.SerializeToString(), "application/x-protobuf"
        ))
    assert [item["adapter_id"] for item in samples] == ["claude-code", "codex"]
    assert samples[0]["payload"]["total_tokens"] == 120
    assert samples[1]["payload"]["total_tokens"] == 230
    serialized = json.dumps(samples)
    assert "must never persist" not in serialized
    assert "private@example.com" not in serialized


def test_json_and_protobuf_decode_to_the_same_sample():
    from google.protobuf.json_format import MessageToDict

    request = _batch("codex")
    protobuf_samples = receiver.decode_logs(
        request.SerializeToString(), "application/x-protobuf"
    )
    json_samples = receiver.decode_logs(
        json.dumps(MessageToDict(request)).encode(), "application/json"
    )
    assert json_samples == protobuf_samples


def test_recording_is_adapter_owned_and_idempotent():
    directory = Path(tempfile.mkdtemp())
    paths = {
        "claude-code": directory / "claude/telemetry.db",
        "codex": directory / "codex/telemetry.db",
    }
    samples = []
    for adapter_id in paths:
        request = _batch(adapter_id)
        samples.extend(receiver.decode_logs(
            request.SerializeToString(), "application/x-protobuf"
        ))
    first = receiver.record_samples(samples, paths)
    second = receiver.record_samples(samples, paths)
    assert first == {"written": 2, "deduplicated": 0, "failed": 0}
    assert second == {"written": 0, "deduplicated": 2, "failed": 0}
    for adapter_id, path in paths.items():
        report = telemetry_data.build_report(path, adapter_id=adapter_id)
        assert report["records"] == 1
        assert report["token_usage"]["evidence"] == "exact"
        raw = path.read_bytes()
        assert b"must never persist" not in raw
        assert b"private@example.com" not in raw


def _harness_batch(adapter_id, event_name, attributes):
    from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
        ExportLogsServiceRequest,
    )

    request = ExportLogsServiceRequest()
    resource = request.resource_logs.add()
    _attribute(resource.resource.attributes, "service.name", adapter_id)
    record = resource.scope_logs.add().log_records.add()
    record.time_unix_nano = 987654
    _attribute(record.attributes, "event.name", event_name)
    for key, value in attributes.items():
        _attribute(record.attributes, key, value)
    return request


def test_claude_usage_keeps_exact_cost_and_duration():
    samples = receiver.decode_logs(
        _batch("claude-code").SerializeToString(), "application/x-protobuf")
    payload = samples[0]["payload"]
    assert payload["cost_micro_usd"] == 4200
    assert payload["duration_ms"] == 1500


def test_codex_usage_omits_cost_instead_of_reporting_zero():
    samples = receiver.decode_logs(
        _batch("codex").SerializeToString(), "application/x-protobuf")
    # Codex publishes no cost attribute. An absent field is the honest encoding;
    # a zero would be indistinguishable from a genuinely free request.
    assert "cost_micro_usd" not in samples[0]["payload"]


def test_tool_and_hook_signals_are_captured_without_content():
    request = _harness_batch("claude-code", "claude_code.tool_result", {
        "tool_name": "Bash", "success": "true", "duration_ms": "42",
        "tool_input_size_bytes": "100", "tool_result_size_bytes": "200",
        "user.email": "private@example.com",
    })
    result = receiver.decode_logs(request.SerializeToString(), "application/x-protobuf")
    assert len(result) == 1 and result[0]["event"] == "tool_result"
    assert result[0]["payload"]["success"] is True
    assert result[0]["payload"]["duration_ms"] == 42
    assert "private@example.com" not in json.dumps(result)

    request = _harness_batch("codex", "codex.tool_decision", {
        "tool_name": "exec", "decision": "Approved", "source": "Config",
    })
    decision = receiver.decode_logs(request.SerializeToString(), "application/x-protobuf")
    assert decision[0]["event"] == "tool_decision"
    assert decision[0]["payload"]["decision"] == "approved"

    request = _harness_batch("claude-code", "claude_code.hook_execution_complete", {
        "hook_event": "PreToolUse", "hook_name": "PreToolUse:Edit", "num_hooks": "9",
        "num_success": "8", "num_blocking": "1", "num_non_blocking_error": "2",
        "num_cancelled": "0", "total_duration_ms": "72",
    })
    hooks = receiver.decode_logs(request.SerializeToString(), "application/x-protobuf")
    assert hooks[0]["event"] == "hook_execution"
    assert hooks[0]["payload"]["errors"] == 2
    assert hooks[0]["payload"]["hooks"] == 9


def test_permission_audit_keeps_exact_input_locally_and_labels_inference():
    directory = Path(tempfile.mkdtemp())
    paths = {
        "claude-code": directory / "claude/telemetry.db",
        "codex": directory / "codex/telemetry.db",
    }
    old = {
        "MAINFRAME_TELEMETRY_DB": os.environ.get("MAINFRAME_TELEMETRY_DB"),
        "MAINFRAME_CODEX_TELEMETRY_DB": os.environ.get("MAINFRAME_CODEX_TELEMETRY_DB"),
    }
    try:
        os.environ["MAINFRAME_TELEMETRY_DB"] = str(paths["claude-code"])
        os.environ["MAINFRAME_CODEX_TELEMETRY_DB"] = str(paths["codex"])
        for adapter_id, command in (
            ("claude-code", "ssh example.invalid"),
            ("codex", "git worktree prune --dry-run"),
        ):
            hooklib = receiver.HOOKLIBS[adapter_id]
            assert hooklib.record_permission_request({
                "session_id": adapter_id + "-session",
                "permission_mode": "default",
                "tool_name": "Bash",
                "tool_input": {"command": command},
                "cwd": str(directory),
            }) == "written"
            assert hooklib.record_permission_decision({
                "session_id": adapter_id + "-session",
                "tool_name": "exec_command" if adapter_id == "codex" else "Bash",
                "decision": "approved" if adapter_id == "codex" else "accept",
                "source": "User" if adapter_id == "codex" else "user_temporary",
            }) == "updated"
            audit = telemetry_data.build_permission_audit(paths[adapter_id], adapter_id)
            assert audit["requests"] == 1 and audit["accepted"] == 1
            row = audit["records"][0]
            assert json.loads(row["tool_input"])["command"] == command
            assert row["correlation_evidence"] == "inferred-session-tool-time"
            assert row["rule_evidence"] == "unavailable" and row["rule_match"] == ""
            assert row["decision_evidence"] == "native-otel"
            assert os.stat(paths[adapter_id]).st_mode & 0o777 == 0o600
        claude = receiver.HOOKLIBS["claude-code"]
        assert claude.record_permission_denied({
            "session_id": "claude-denied", "tool_use_id": "tool-42",
            "permission_mode": "default", "tool_name": "Bash",
            "tool_input": {"command": "rm protected-file"}, "reason": "policy",
        }) == "written"
        assert claude.record_permission_decision({
            "session_id": "claude-denied", "tool_use_id": "tool-42",
            "tool_name": "Bash", "decision": "reject", "source": "hook",
        }) == "updated"
        audit = telemetry_data.build_permission_audit(paths["claude-code"], "claude-code")
        denied = next(row for row in audit["records"] if row["request_kind"] == "auto_denial")
        assert denied["correlation_evidence"] == "exact-tool-use-id"
        assert denied["decision_source"] == "hook"
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_codex_tool_result_never_stores_arguments_or_output():
    request = _harness_batch("codex", "codex.tool_result", {
        "tool_name": "exec", "success": "true", "duration_ms": "10",
        "arguments": "must never persist", "output": "must never persist",
    })
    result = receiver.decode_logs(request.SerializeToString(), "application/x-protobuf")
    assert "must never persist" not in json.dumps(result)


def test_ingest_health_separates_a_broken_collector_from_an_idle_one():
    directory = Path(tempfile.mkdtemp())
    paths = {
        "claude-code": directory / "claude/telemetry.db",
        "codex": directory / "codex/telemetry.db",
    }
    health = receiver.IngestHealth(directory / "ingest.json")
    assert health.snapshot()["batches"] == 0

    receiver.ingest_batch(
        health, _batch("claude-code").SerializeToString(),
        "application/x-protobuf", paths)
    state = health.snapshot()
    assert state["batches_decoded"] == 1 and state["batches_failed"] == 0
    assert state["rows_written"] == 1

    receiver.ingest_batch(health, b"not-a-batch", "application/json", paths)
    state = health.snapshot()
    assert state["batches_failed"] == 1
    assert state["last_reason"] == "malformed-batch"
    assert state["by_protocol"]["json"]["failed"] == 1

    stored = receiver.read_ingest_health(directory / "ingest.json")
    assert stored["evidence"] == "observed" and stored["healthy"] is False
    # An untouched collector is idle, not broken; a restart must not alarm.
    assert receiver.IngestHealth().snapshot()["batches"] == 0
    assert otlp_ingest_health.is_healthy({"batches": 0, "batches_failed": 0}) is None
    assert receiver.read_ingest_health(directory / "absent.json") == {
        "evidence": "unknown", "healthy": None,
    }


def test_a_missing_decoder_dependency_is_reported_not_swallowed():
    # The failure that hid every Codex batch for a day: an interpreter without
    # the protobuf decoder raised, and the exception was discarded whole.
    health = receiver.IngestHealth()
    original = receiver.decode_logs

    def explode(_body, _content_type):
        raise ModuleNotFoundError("No module named 'opentelemetry'")

    receiver.decode_logs = explode
    try:
        receiver.ingest_batch(health, b"payload", "application/x-protobuf", {})
    finally:
        receiver.decode_logs = original
    state = health.snapshot()
    assert state["batches_failed"] == 1
    assert state["last_reason"] == "dependency-missing"
    assert state["last_error_kind"] == "ModuleNotFoundError"


def test_replayed_harness_batches_are_deduplicated():
    directory = Path(tempfile.mkdtemp())
    paths = {
        "claude-code": directory / "claude/telemetry.db",
        "codex": directory / "codex/telemetry.db",
    }
    request = _harness_batch("claude-code", "claude_code.tool_result", {
        "tool_name": "Bash", "success": "true", "duration_ms": "42",
        "tool_use_id": "toolu_1",
    })
    body = request.SerializeToString()
    samples = receiver.decode_logs(body, "application/x-protobuf")
    assert receiver.record_samples(samples, paths)["written"] == 1
    assert receiver.record_samples(samples, paths)["deduplicated"] == 1


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK native telemetry receiver - {len(tests)} tests passed")


if __name__ == "__main__":
    main()
