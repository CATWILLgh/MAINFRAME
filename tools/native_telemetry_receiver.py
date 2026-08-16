#!/usr/bin/env python3
"""Receive local OTLP logs and retain only privacy-safe model usage counters."""

from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
MAX_REQUEST_BYTES = 4 * 1024 * 1024


def _load_hooklib(adapter_id: str):
    script = {
        "claude-code": ROOT / "adapters/claude-code/plugin/hooks/scripts/_hooklib.py",
        "codex": ROOT / "adapters/codex/hooks/scripts/_hooklib.py",
    }[adapter_id]
    path = str(script.parent)
    old_contract = sys.modules.pop("_telemetry_contract", None)
    sys.path.insert(0, path)
    try:
        spec = importlib.util.spec_from_file_location(
            f"mainframe_native_telemetry_{adapter_id.replace('-', '_')}", script
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {adapter_id} telemetry sink")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(path)
        sys.modules.pop("_telemetry_contract", None)
        if old_contract is not None:
            sys.modules["_telemetry_contract"] = old_contract


HOOKLIBS = {
    "claude-code": _load_hooklib("claude-code"),
    "codex": _load_hooklib("codex"),
}


def _value(value):
    if not isinstance(value, dict):
        return None
    for key in (
        "stringValue", "intValue", "doubleValue", "boolValue",
        "string_value", "int_value", "double_value", "bool_value",
    ):
        if key in value:
            raw = value[key]
            if key.endswith("intValue") or key.endswith("int_value"):
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    return None
            return raw
    return None


def _attributes(rows):
    result = {}
    for item in rows or []:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        result[item["key"]] = _value(item.get("value"))
    return result


def _children(value, camel, snake):
    if not isinstance(value, dict):
        return []
    rows = value.get(camel, value.get(snake, []))
    return rows if isinstance(rows, list) else []


def _event_name(body, attrs, resource):
    candidates = (
        attrs.get("event.name"),
        _value(body),
        resource.get("service.name"),
    )
    for candidate in candidates:
        text = str(candidate or "")
        if text.startswith(("claude_code.", "codex.")):
            return text
    service = str(resource.get("service.name") or "")
    short = str(attrs.get("event.name") or "")
    if service.startswith("claude") and short:
        return "claude_code." + short.removeprefix("claude_code.")
    if service.startswith("codex") and short:
        return "codex." + short.removeprefix("codex.")
    return ""


def _count(attrs, *keys):
    for key in keys:
        value = attrs.get(key)
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        return max(0, number)
    return 0


def _sample(adapter_id, event_name, attrs, record):
    if adapter_id == "claude-code":
        if event_name != "claude_code.api_request":
            return None
        input_tokens = _count(attrs, "input_tokens")
        output_tokens = _count(attrs, "output_tokens")
        usage = {
            "input_tokens": input_tokens,
            "cached_input_tokens": _count(attrs, "cache_read_tokens"),
            "cache_write_tokens": _count(attrs, "cache_creation_tokens"),
            "output_tokens": output_tokens,
            "reasoning_output_tokens": 0,
            "total_tokens": input_tokens + output_tokens,
        }
        session = str(attrs.get("session.id") or "")
        native_id = str(
            attrs.get("request_id") or attrs.get("client_request_id") or ""
        )
    else:
        if event_name != "codex.sse_event" or str(attrs.get("event.kind")) != "response.completed":
            return None
        input_tokens = _count(attrs, "input_token_count")
        output_tokens = _count(attrs, "output_token_count")
        usage = {
            "input_tokens": input_tokens,
            "cached_input_tokens": _count(attrs, "cached_token_count"),
            "cache_write_tokens": _count(attrs, "cache_write_token_count"),
            "output_tokens": output_tokens,
            "reasoning_output_tokens": _count(attrs, "reasoning_token_count"),
            "total_tokens": _count(attrs, "tool_token_count") or input_tokens + output_tokens,
        }
        session = str(attrs.get("conversation.id") or "")
        native_id = str(attrs.get("response.id") or "")
    if not any(usage.values()):
        return None
    identity = {
        "adapter": adapter_id,
        "event": event_name,
        "session": session,
        "native_id": native_id,
        "time": record.get("timeUnixNano", record.get("time_unix_nano", "")),
        "model": str(attrs.get("model") or attrs.get("gen_ai.request.model") or ""),
        "usage": usage,
    }
    return {
        "adapter_id": adapter_id,
        "session_id": session,
        "model": identity["model"],
        "payload": {
            "sample_id": hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "source": "native-otel",
            "request_count": 1,
            **usage,
        },
    }


def decode_logs(body: bytes, content_type: str) -> list[dict]:
    """Decode one OTLP batch in memory and return only allowlisted counters."""
    if "json" in content_type:
        value = json.loads(body.decode("utf-8"))
    else:
        from google.protobuf.json_format import MessageToDict
        from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
            ExportLogsServiceRequest,
        )

        message = ExportLogsServiceRequest()
        message.ParseFromString(body)
        value = MessageToDict(message, preserving_proto_field_name=False)

    samples = []
    for resource_logs in _children(value, "resourceLogs", "resource_logs"):
        resource = _attributes(
            (resource_logs.get("resource") or {}).get("attributes", [])
        )
        for scope_logs in _children(resource_logs, "scopeLogs", "scope_logs"):
            for record in _children(scope_logs, "logRecords", "log_records"):
                attrs = {**resource, **_attributes(record.get("attributes", []))}
                event_name = _event_name(record.get("body"), attrs, resource)
                adapter_id = (
                    "claude-code" if event_name.startswith("claude_code.")
                    else "codex" if event_name.startswith("codex.")
                    else ""
                )
                if adapter_id:
                    sample = _sample(adapter_id, event_name, attrs, record)
                    if sample is not None:
                        samples.append(sample)
    return samples


def record_samples(samples: list[dict], db_paths: dict[str, Path]) -> dict[str, int]:
    results = {"written": 0, "deduplicated": 0, "failed": 0}
    old = {
        "MAINFRAME_TELEMETRY_DB": os.environ.get("MAINFRAME_TELEMETRY_DB"),
        "MAINFRAME_TELEMETRY_ORIGIN": os.environ.get("MAINFRAME_TELEMETRY_ORIGIN"),
        "MAINFRAME_CODEX_TELEMETRY_DB": os.environ.get("MAINFRAME_CODEX_TELEMETRY_DB"),
        "MAINFRAME_CODEX_TELEMETRY_ORIGIN": os.environ.get("MAINFRAME_CODEX_TELEMETRY_ORIGIN"),
    }
    try:
        for sample in samples:
            adapter_id = sample["adapter_id"]
            if adapter_id == "claude-code":
                os.environ["MAINFRAME_TELEMETRY_DB"] = str(db_paths[adapter_id])
                os.environ["MAINFRAME_TELEMETRY_ORIGIN"] = "runtime"
            else:
                os.environ["MAINFRAME_CODEX_TELEMETRY_DB"] = str(db_paths[adapter_id])
                os.environ["MAINFRAME_CODEX_TELEMETRY_ORIGIN"] = "runtime"
            status = HOOKLIBS[adapter_id].log_event(
                "model_usage",
                sample["payload"],
                {"session_id": sample["session_id"], "model": sample["model"]},
            )
            results[status if status in results else "failed"] += 1
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return results


class Receiver(BaseHTTPRequestHandler):
    db_paths: dict[str, Path] = {}
    health_token = ""

    def log_message(self, _format, *_args):
        return

    def _reply(self, status=200, *, health=False):
        self.send_response(status)
        if health and self.health_token:
            self.send_header("X-Mainframe-Instance", self.health_token)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._reply(200 if self.path == "/health" else 404, health=self.path == "/health")

    def do_POST(self):
        if self.path != "/v1/logs":
            self._reply(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._reply(200)
            return
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._reply(200)
            return
        try:
            samples = decode_logs(
                self.rfile.read(length), self.headers.get("Content-Type", "")
            )
            record_samples(samples, self.db_paths)
        except Exception:
            # The exporter is asynchronous. Analytics must never interrupt work
            # or trigger an unbounded retry loop because one batch was malformed.
            pass
        self._reply(200)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4318)
    parser.add_argument("--health-token", default="")
    parser.add_argument(
        "--claude-db",
        default=str(ROOT / "workspace/runtime/claude-code/telemetry/telemetry.db"),
    )
    parser.add_argument(
        "--codex-db",
        default=str(ROOT / "workspace/runtime/codex/telemetry/telemetry.db"),
    )
    args = parser.parse_args(argv)
    Receiver.db_paths = {
        "claude-code": Path(args.claude_db).expanduser().resolve(),
        "codex": Path(args.codex_db).expanduser().resolve(),
    }
    Receiver.health_token = args.health_token
    server = ThreadingHTTPServer((args.host, args.port), Receiver)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
