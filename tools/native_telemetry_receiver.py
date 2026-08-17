#!/usr/bin/env python3
"""Receive local OTLP logs and retain only privacy-safe model usage counters."""

from __future__ import annotations

import argparse
import hashlib
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

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


def _present(attrs, *keys):
    """None when the harness did not report the counter, so absence stays absent."""
    for key in keys:
        if key not in attrs:
            continue
        try:
            return max(0, int(attrs[key]))
        except (TypeError, ValueError):
            continue
    return None


def _flag(attrs, key):
    """OTLP attributes arrive as 'true'/'false' strings as often as booleans."""
    value = attrs.get(key)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    return None


def _text(attrs, *keys, limit=120):
    for key in keys:
        value = attrs.get(key)
        text = str(value or "").strip()
        if text:
            return text[:limit]
    return ""


def _sample_id(adapter_id, event_name, native_id, record, extra):
    identity = {
        "adapter": adapter_id,
        "event": event_name,
        "native_id": native_id,
        "time": record.get("timeUnixNano", record.get("time_unix_nano", "")),
        "extra": extra,
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _session_of(adapter_id, attrs):
    return str((
        attrs.get("session.id") if adapter_id == "claude-code"
        else attrs.get("conversation.id")
    ) or "")


def _usage_sample(adapter_id, event_name, attrs, record):
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
        native_id = str(
            attrs.get("request_id") or attrs.get("client_request_id") or ""
        )
        # Claude Code reports exact billing in integer micro-dollars; the float
        # cost_usd beside it is the same number and is not stored.
        cost = _present(attrs, "cost_usd_micros")
        duration = _present(attrs, "duration_ms")
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
        native_id = str(attrs.get("response.id") or "")
        # Codex publishes no cost attribute; the field stays absent rather than 0.
        cost = None
        duration = _present(attrs, "ttft_ms")
    if not any(usage.values()):
        return None
    session = _session_of(adapter_id, attrs)
    model = _text(attrs, "model", "gen_ai.request.model")
    payload = {
        "sample_id": _sample_id(
            adapter_id, event_name, native_id, record,
            {"session": session, "model": model, "usage": usage},
        ),
        "source": "native-otel",
        "request_count": 1,
        **usage,
    }
    if cost is not None:
        payload["cost_micro_usd"] = cost
    if duration is not None:
        payload["duration_ms"] = duration
    return {
        "adapter_id": adapter_id, "event": "model_usage",
        "session_id": session, "model": model, "payload": payload,
    }


def _harness_sample(adapter_id, event_name, attrs, record):
    """Tool and hook execution facts — names, outcomes and sizes, never content."""
    short = event_name.split(".", 1)[-1]
    session = _session_of(adapter_id, attrs)
    model = _text(attrs, "model")
    common = {"adapter_id": adapter_id, "session_id": session, "model": model}

    if short == "tool_result":
        tool = _text(attrs, "tool_name")
        success = _flag(attrs, "success")
        duration = _present(attrs, "duration_ms")
        if not tool or success is None or duration is None:
            return None
        payload = {
            "sample_id": _sample_id(
                adapter_id, event_name,
                _text(attrs, "tool_use_id", "call_id"), record,
                {"tool": tool, "success": success},
            ),
            "tool_name": tool, "success": success, "duration_ms": duration,
        }
        for field, keys in (
            ("input_bytes", ("tool_input_size_bytes",)),
            ("output_bytes", ("tool_result_size_bytes",)),
        ):
            value = _present(attrs, *keys)
            if value is not None:
                payload[field] = value
        return {**common, "event": "tool_result", "payload": payload}

    if short == "tool_decision":
        tool = _text(attrs, "tool_name")
        decision = _text(attrs, "decision", limit=48).lower()
        if not tool or not decision:
            return None
        payload = {
            "sample_id": _sample_id(
                adapter_id, event_name,
                _text(attrs, "tool_use_id", "call_id"), record,
                {"tool": tool, "decision": decision},
            ),
            "tool_name": tool, "decision": decision,
        }
        source = _text(attrs, "source", limit=48)
        if source:
            payload["source"] = source
        return {**common, "event": "tool_decision", "payload": payload}

    if adapter_id == "claude-code" and short == "hook_execution_complete":
        hook_event = _text(attrs, "hook_event", limit=48)
        counts = {
            "hooks": _present(attrs, "num_hooks"),
            "succeeded": _present(attrs, "num_success"),
            "blocking": _present(attrs, "num_blocking"),
            "errors": _present(attrs, "num_non_blocking_error"),
            "cancelled": _present(attrs, "num_cancelled"),
            "duration_ms": _present(attrs, "total_duration_ms"),
        }
        if not hook_event or any(value is None for value in counts.values()):
            return None
        payload = {
            "sample_id": _sample_id(
                adapter_id, event_name,
                _text(attrs, "hook_name", limit=64), record,
                {"sequence": attrs.get("event.sequence"), **counts},
            ),
            "hook_event": hook_event, **counts,
        }
        return {**common, "event": "hook_execution", "payload": payload}
    return None


def _samples(adapter_id, event_name, attrs, record):
    usage = _usage_sample(adapter_id, event_name, attrs, record)
    if usage is not None:
        return [usage]
    harness = _harness_sample(adapter_id, event_name, attrs, record)
    return [harness] if harness is not None else []


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
                    samples.extend(_samples(adapter_id, event_name, attrs, record))
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
                sample.get("event", "model_usage"),
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


def ingest_batch(health, body, content_type, db_paths):
    """Decode and store one batch, recording the outcome either way.

    The exporter is asynchronous, so a failure must never propagate back to the
    harness or trigger an unbounded retry loop — but it must still be counted.
    """
    try:
        samples = decode_logs(body, content_type)
    except Exception as error:
        health.batch(content_type, error=error)
        return {"written": 0, "deduplicated": 0, "failed": 0}
    try:
        results = record_samples(samples, db_paths)
    except Exception as error:
        health.batch(content_type, error=error)
        return {"written": 0, "deduplicated": 0, "failed": len(samples)}
    health.batch(content_type, rows=len(samples), results=results)
    return results


class IngestHealth:
    """Counts OTLP batch outcomes so an empty panel can name its own cause.

    A decode failure used to be swallowed whole: a serving interpreter without
    the protobuf dependency dropped every binary batch — all Codex traffic —
    while JSON batches kept working, and the page reported zero usage as if the
    harness had simply been idle. Only exception classes and a fixed reason code
    are retained; batch bytes never reach this record.
    """

    REASONS = {"dependency-missing", "malformed-batch", "sink-unavailable"}

    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self._state = {
            # Counters live in memory, so they describe the current collector
            # process rather than all time; started_at says which window it is.
            "started_at": self._now(),
            "batches": 0, "batches_decoded": 0, "batches_failed": 0,
            "rows_written": 0, "rows_deduplicated": 0, "rows_failed": 0,
            "by_protocol": {},
            "last_batch_at": "", "last_failure_at": "",
            "last_error_kind": "", "last_reason": "",
        }

    @staticmethod
    def _now():
        return datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _protocol(content_type):
        return "json" if "json" in (content_type or "") else "protobuf"

    def _protocol_bucket(self, protocol):
        return self._state["by_protocol"].setdefault(
            protocol, {"batches": 0, "decoded": 0, "failed": 0, "rows": 0})

    def batch(self, content_type, *, rows=0, results=None, error=None):
        protocol = self._protocol(content_type)
        with self._lock:
            state = self._state
            bucket = self._protocol_bucket(protocol)
            state["batches"] += 1
            bucket["batches"] += 1
            state["last_batch_at"] = self._now()
            if error is not None:
                state["batches_failed"] += 1
                bucket["failed"] += 1
                state["last_failure_at"] = state["last_batch_at"]
                state["last_error_kind"] = type(error).__name__
                state["last_reason"] = (
                    "dependency-missing"
                    if isinstance(error, (ImportError, ModuleNotFoundError))
                    else "malformed-batch"
                )
            else:
                state["batches_decoded"] += 1
                bucket["decoded"] += 1
                bucket["rows"] += rows
                for key, name in (
                    ("written", "rows_written"),
                    ("deduplicated", "rows_deduplicated"),
                    ("failed", "rows_failed"),
                ):
                    state[name] += (results or {}).get(key, 0)
                if (results or {}).get("failed"):
                    state["last_failure_at"] = state["last_batch_at"]
                    state["last_reason"] = "sink-unavailable"
        self._persist()

    def snapshot(self):
        with self._lock:
            return json.loads(json.dumps(self._state))

    def _persist(self):
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(f".tmp-{os.getpid()}")
            temporary.write_text(
                json.dumps(self.snapshot(), ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            pass


def read_ingest_health(path):
    """Report the collector's own state; 'unknown' when it never ran."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("ingest health is not an object")
    except (OSError, ValueError):
        return {"evidence": "unknown", "healthy": None}
    failed = int(value.get("batches_failed") or 0)
    batches = int(value.get("batches") or 0)
    return {
        "evidence": "observed",
        "healthy": batches > 0 and failed == 0,
        **value,
    }


class Receiver(BaseHTTPRequestHandler):
    db_paths: dict[str, Path] = {}
    health_token = ""
    ingest = IngestHealth()

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
        ingest_batch(
            self.ingest, self.rfile.read(length),
            self.headers.get("Content-Type", ""), self.db_paths,
        )
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
