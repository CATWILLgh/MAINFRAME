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

from otlp_ingest_health import IngestHealth, read_ingest_health
from otlp_samples import attributes, children, resolve_event_name, samples

ROOT = Path(__file__).resolve().parent.parent
MAX_REQUEST_BYTES = 4 * 1024 * 1024


def _load_hooklib(adapter_id: str):
    script = {
        "claude-code": ROOT / "adapters/claude-code/plugin/hooks/scripts/_hooklib.py",
        "codex": ROOT / "adapters/codex/hooks/scripts/_hooklib.py",
    }[adapter_id]
    path = str(script.parent)
    old_contract = sys.modules.pop("_telemetry_contract", None)
    old_permission = sys.modules.pop("_permission_audit", None)
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
        sys.modules.pop("_permission_audit", None)
        if old_contract is not None:
            sys.modules["_telemetry_contract"] = old_contract
        if old_permission is not None:
            sys.modules["_permission_audit"] = old_permission


HOOKLIBS = {
    "claude-code": _load_hooklib("claude-code"),
    "codex": _load_hooklib("codex"),
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

    decoded = []
    for resource_logs in children(value, "resourceLogs", "resource_logs"):
        resource = attributes(
            (resource_logs.get("resource") or {}).get("attributes", [])
        )
        for scope_logs in children(resource_logs, "scopeLogs", "scope_logs"):
            for record in children(scope_logs, "logRecords", "log_records"):
                attrs = {**resource, **attributes(record.get("attributes", []))}
                name = resolve_event_name(record.get("body"), attrs, resource)
                adapter_id = (
                    "claude-code" if name.startswith("claude_code.")
                    else "codex" if name.startswith("codex.")
                    else ""
                )
                if adapter_id:
                    decoded.extend(samples(adapter_id, name, attrs, record))
    return decoded


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
                {
                    "session_id": sample["session_id"], "model": sample["model"],
                    "tool_use_id": sample.get("tool_use_id", ""),
                },
            )
            results[status if status in results else "failed"] += 1
            if sample.get("event") == "tool_decision":
                HOOKLIBS[adapter_id].record_permission_decision({
                    "session_id": sample.get("session_id", ""),
                    "tool_use_id": sample.get("tool_use_id", ""),
                    "timestamp": sample.get("timestamp", ""),
                    "tool_name": sample["payload"].get("tool_name", ""),
                    "decision": sample["payload"].get("decision", ""),
                    "source": sample["payload"].get("source", "unknown"),
                })
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
