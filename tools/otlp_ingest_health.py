#!/usr/bin/env python3
"""Track whether the local OTLP collector is actually accepting batches.

Kept apart from decoding so the question "is collection working?" has one owner
and one on-disk record, readable by a static page build that never ran a server.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import threading


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
    return {"evidence": "observed", "healthy": is_healthy(value), **value}


def is_healthy(state):
    """True/False once a batch has arrived, None while nothing has yet.

    A collector that has not been sent anything is idle, not broken; collapsing
    the two would raise a false alarm every time the service restarts.
    """
    if int(state.get("batches") or 0) <= 0:
        return None
    return int(state.get("batches_failed") or 0) == 0
