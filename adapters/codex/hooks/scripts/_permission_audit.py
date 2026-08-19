"""Local dev-only permission audit storage.

This table is intentionally separate from the privacy-safe telemetry stream:
it retains exact tool input so a human can assess permission false positives.
Nothing here is an authorization mechanism.
"""

import datetime
import hashlib
import json
import os
import re
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS permission_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  adapter_id TEXT NOT NULL,
  request_ts TEXT NOT NULL,
  updated_ts TEXT NOT NULL,
  session_id TEXT,
  turn_id TEXT,
  tool_use_id TEXT,
  project TEXT,
  tool_name TEXT NOT NULL,
  normalized_tool_name TEXT NOT NULL,
  permission_mode TEXT,
  tool_input TEXT NOT NULL,
  input_sha256 TEXT NOT NULL,
  request_kind TEXT NOT NULL,
  decision TEXT,
  decision_source TEXT,
  decision_ts TEXT,
  wait_ms INTEGER,
  wait_evidence TEXT NOT NULL,
  decision_evidence TEXT NOT NULL,
  correlation_evidence TEXT NOT NULL,
  runtime_reason TEXT,
  rule_match TEXT,
  rule_evidence TEXT NOT NULL
)
"""


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _parse_ts(value):
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _project(cwd):
    if not cwd:
        return ""
    normalized = os.path.normpath(str(cwd))
    digest = hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()[:6]
    return f"{os.path.basename(normalized)}-{digest}"


def normalize_tool_name(value):
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return {
        "bash": "exec_command",
        "shell": "exec_command",
        "exec": "exec_command",
        "write": "write_file",
        "edit": "edit_file",
    }.get(text, text or "unknown")


def initialize(db):
    directory = os.path.dirname(str(db))
    os.makedirs(directory, mode=0o700, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    connection = sqlite3.connect(db, timeout=5)
    try:
        connection.execute(SCHEMA)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_permission_audit_session_tool "
            "ON permission_audit(session_id, normalized_tool_name, request_ts)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_permission_audit_decision_ts "
            "ON permission_audit(decision_ts)"
        )
        connection.commit()
    finally:
        connection.close()
    try:
        os.chmod(db, 0o600)
    except OSError:
        pass


def record_request(db, adapter_id, payload):
    initialize(db)
    ts = _now()
    tool_input = json.dumps(
        payload.get("tool_input") or {}, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"),
    )
    tool_name = str(payload.get("tool_name") or "unknown")
    row = (
        adapter_id, ts, ts, str(payload.get("session_id") or ""),
        str(payload.get("turn_id") or payload.get("prompt_id") or ""),
        str(payload.get("tool_use_id") or ""), _project(payload.get("cwd") or ""),
        tool_name, normalize_tool_name(tool_name),
        str(payload.get("permission_mode") or "unknown"), tool_input,
        hashlib.sha256(tool_input.encode("utf-8")).hexdigest(), "prompt",
        None, None, None, None, "unavailable", "pending", "unresolved",
        "", "", "unavailable",
    )
    connection = sqlite3.connect(db, timeout=1)
    try:
        connection.execute(
            "INSERT INTO permission_audit("
            "adapter_id,request_ts,updated_ts,session_id,turn_id,tool_use_id,project,"
            "tool_name,normalized_tool_name,permission_mode,tool_input,input_sha256,"
            "request_kind,decision,decision_source,decision_ts,wait_ms,wait_evidence,"
            "decision_evidence,correlation_evidence,runtime_reason,rule_match,rule_evidence"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row,
        )
        connection.commit()
        return "written"
    finally:
        connection.close()


def record_denied(db, adapter_id, payload):
    """Record Claude auto-mode denial as an exact standalone runtime fact."""
    initialize(db)
    ts = _now()
    tool_input = json.dumps(
        payload.get("tool_input") or {}, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"),
    )
    tool_name = str(payload.get("tool_name") or "unknown")
    connection = sqlite3.connect(db, timeout=1)
    try:
        connection.execute(
            "INSERT INTO permission_audit("
            "adapter_id,request_ts,updated_ts,session_id,turn_id,tool_use_id,project,"
            "tool_name,normalized_tool_name,permission_mode,tool_input,input_sha256,"
            "request_kind,decision,decision_source,decision_ts,wait_ms,wait_evidence,"
            "decision_evidence,correlation_evidence,runtime_reason,rule_match,rule_evidence"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                adapter_id, ts, ts, str(payload.get("session_id") or ""),
                str(payload.get("turn_id") or payload.get("prompt_id") or ""),
                str(payload.get("tool_use_id") or ""), _project(payload.get("cwd") or ""),
                tool_name, normalize_tool_name(tool_name),
                str(payload.get("permission_mode") or "unknown"), tool_input,
                hashlib.sha256(tool_input.encode("utf-8")).hexdigest(), "auto_denial",
                "reject", "runtime", ts, None, "unavailable",
                "permission-denied-hook", "exact-tool-use-id", str(payload.get("reason") or ""),
                "", "unavailable",
            ),
        )
        connection.commit()
        return "written"
    finally:
        connection.close()


def record_decision(db, adapter_id, sample):
    """Attach an exact native decision to a request using bounded correlation."""
    initialize(db)
    ts = str(sample.get("timestamp") or _now())
    session_id = str(sample.get("session_id") or "")
    tool_use_id = str(sample.get("tool_use_id") or "")
    normalized = normalize_tool_name(sample.get("tool_name"))
    connection = sqlite3.connect(db, timeout=1)
    connection.row_factory = sqlite3.Row
    try:
        candidate = None
        correlation = "unresolved"
        if tool_use_id:
            candidate = connection.execute(
                "SELECT * FROM permission_audit WHERE adapter_id=? AND tool_use_id=? "
                "ORDER BY id DESC LIMIT 1",
                (adapter_id, tool_use_id),
            ).fetchone()
            if candidate is not None:
                correlation = "exact-tool-use-id"
        if candidate is None and session_id:
            rows = connection.execute(
                "SELECT * FROM permission_audit WHERE adapter_id=? AND session_id=? "
                "AND normalized_tool_name=? AND decision IS NULL AND request_ts<=? "
                "ORDER BY request_ts DESC LIMIT 2",
                (adapter_id, session_id, normalized, ts),
            ).fetchall()
            decision_time = _parse_ts(ts)
            rows = [row for row in rows if decision_time and _parse_ts(row["request_ts"])
                    and 0 <= (decision_time - _parse_ts(row["request_ts"])).total_seconds() <= 600]
            if rows:
                candidate = rows[0]
                correlation = "inferred-session-tool-time"
        if candidate is None:
            return "unresolved"
        request_time = _parse_ts(candidate["request_ts"])
        decision_time = _parse_ts(ts)
        wait_ms = None
        wait_evidence = "unavailable"
        if request_time and decision_time and decision_time >= request_time:
            wait_ms = int((decision_time - request_time).total_seconds() * 1000)
            wait_evidence = "inferred-between-events"
        connection.execute(
            "UPDATE permission_audit SET updated_ts=?,tool_use_id=COALESCE(NULLIF(?,''),tool_use_id),"
            "decision=?,decision_source=?,decision_ts=?,wait_ms=?,wait_evidence=?,"
            "decision_evidence='native-otel',correlation_evidence=?,rule_match='',"
            "rule_evidence='unavailable' WHERE id=?",
            (
                _now(), tool_use_id, str(sample.get("decision") or ""),
                str(sample.get("source") or "unknown"), ts, wait_ms,
                wait_evidence, correlation, candidate["id"],
            ),
        )
        connection.commit()
        return "updated"
    finally:
        connection.close()
