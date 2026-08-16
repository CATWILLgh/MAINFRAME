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


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK native telemetry receiver - {len(tests)} tests passed")


if __name__ == "__main__":
    main()
