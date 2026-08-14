#!/usr/bin/env python3
"""Read MAINFRAME Claude telemetry as one validated summary or JSONL stream."""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "adapters" / "claude-code" / "plugin" / "hooks" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _telemetry_contract import EVENT_FIELDS, ROW_SCHEMA_VERSION, validate_payload  # noqa: E402

INSTALLED_DB = Path("~/.claude/mainframe/claude-code/telemetry/telemetry.db").expanduser()
REPOSITORY_DB = ROOT / "workspace" / "runtime" / "claude-code" / "telemetry" / "telemetry.db"

BREAKDOWN_FIELDS = {
    "session": ("phase",),
    "compaction": ("trigger",),
    "auto_permission_denied": ("tool_name",),
    "skill_request": ("skill", "invoker"),
    "ticket_change": ("operation",),
    "code_edit": ("lang", "operation"),
    "init_reminder": ("reminded",),
    "model_lab": ("status",),
}


def default_db_path():
    return INSTALLED_DB if INSTALLED_DB.is_file() else REPOSITORY_DB


def _read_connection(path):
    uri = f"file:{Path(path).resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=1)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _select_columns(connection):
    columns = {row[1] for row in connection.execute("PRAGMA table_info(events)")}
    if not columns:
        raise sqlite3.OperationalError("events table is missing")

    def selected(name, fallback):
        return name if name in columns else f"{fallback} AS {name}"

    return ", ".join((
        "id",
        "ts",
        selected("schema_version", "1"),
        "session_id",
        selected("prompt_id", "''"),
        selected("agent_id", "''"),
        "agent_type",
        selected("tool_use_id", "''"),
        "project",
        selected("hook_event", "''"),
        "event",
        "payload",
    ))


def iter_events(path, after_id=0, limit=None):
    """Yield privacy-safe normalized rows in durable id order."""
    connection = _read_connection(path)
    try:
        selected = _select_columns(connection)
        sql = f"SELECT {selected} FROM events WHERE id > ? ORDER BY id"
        params = [max(0, int(after_id))]
        if limit is not None and int(limit) > 0:
            sql += " LIMIT ?"
            params.append(int(limit))
        for row in connection.execute(sql, params):
            (row_id, timestamp, schema_version, session_id, prompt_id, agent_id,
             agent_type, tool_use_id, project, hook_event, event, raw_payload) = row
            errors = []
            try:
                payload = json.loads(raw_payload or "")
                if not isinstance(payload, dict):
                    raise ValueError("payload is not an object")
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                payload = {}
                errors.append(str(error))

            version = int(schema_version or 1)
            if not errors and version >= ROW_SCHEMA_VERSION:
                try:
                    payload = validate_payload(str(event), payload)
                except ValueError as error:
                    payload = {}
                    errors.append(str(error))

            yield {
                "schema_version": version,
                "id": int(row_id),
                "timestamp": str(timestamp or ""),
                "session_id": str(session_id or ""),
                "prompt_id": str(prompt_id or ""),
                "agent_id": str(agent_id or ""),
                "agent_type": str(agent_type or ""),
                "tool_use_id": str(tool_use_id or ""),
                "project": str(project or ""),
                "source_event": str(hook_event or ""),
                "event": str(event or ""),
                "data": payload,
                "valid": not errors,
                "errors": errors,
            }
    finally:
        connection.close()


def _empty_report(active=False, error=""):
    return {
        "active": active,
        "format_version": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds").replace("+00:00", "Z"),
        "records": 0,
        "usable_records": 0,
        "sessions": 0,
        "agent_instances": 0,
        "first_timestamp": "",
        "last_timestamp": "",
        "last_id": 0,
        "schema_versions": [],
        "legacy_rows": 0,
        "invalid_rows": 0,
        "invalid_examples": [],
        "unknown_events": [],
        "event_counts": [],
        "by_day": [],
        "by_agent": [],
        "agent_lifecycle": [],
        "breakdowns": [],
        "hook_effectiveness": [],
        "recent_events": [],
        "error": error,
    }


def build_report(path, recent_limit=40):
    """Aggregate the same validated stream consumed by the machine CLI and UI."""
    path = Path(path)
    if not path.is_file():
        return _empty_report()

    report = _empty_report(active=True)
    sessions = set()
    agents = set()
    schema_versions = collections.Counter()
    event_counts = collections.Counter()
    days = collections.Counter()
    by_agent = collections.Counter()
    unknown = collections.Counter()
    lifecycle = {}
    breakdowns = {
        (event, field): collections.Counter()
        for event, fields in BREAKDOWN_FIELDS.items() for field in fields
    }
    effectiveness = {}
    recent = collections.deque(maxlen=max(0, int(recent_limit)))

    try:
        rows = iter_events(path)
        for row in rows:
            report["records"] += 1
            report["last_id"] = row["id"]
            report["first_timestamp"] = report["first_timestamp"] or row["timestamp"]
            report["last_timestamp"] = row["timestamp"] or report["last_timestamp"]
            schema_versions[row["schema_version"]] += 1
            if row["schema_version"] < ROW_SCHEMA_VERSION:
                report["legacy_rows"] += 1
            if row["event"] not in EVENT_FIELDS:
                unknown[row["event"] or "(empty)"] += 1

            if not row["valid"]:
                report["invalid_rows"] += 1
                if len(report["invalid_examples"]) < 10:
                    report["invalid_examples"].append({
                        "id": row["id"], "event": row["event"],
                        "errors": row["errors"],
                    })

            usable = (
                row["schema_version"] >= ROW_SCHEMA_VERSION
                and row["valid"] and row["event"] in EVENT_FIELDS
            )
            if not usable:
                continue
            report["usable_records"] += 1
            if row["session_id"]:
                sessions.add(row["session_id"])
            if row["agent_id"]:
                agents.add(row["agent_id"])
            event_counts[row["event"]] += 1
            if row["timestamp"]:
                days[row["timestamp"][:10]] += 1
            role = row["agent_type"] or "(main context)"
            by_agent[role] += 1

            if row["event"] in ("subagent_start", "subagent_stop"):
                item = lifecycle.setdefault(role, {
                    "agent": role, "started": 0, "stopped": 0, "instances": set(),
                })
                item["started" if row["event"] == "subagent_start" else "stopped"] += 1
                if row["agent_id"]:
                    item["instances"].add(row["agent_id"])

            for field in BREAKDOWN_FIELDS.get(row["event"], ()):
                value = row["data"].get(field)
                label = str(value).lower() if isinstance(value, bool) else str(value or "")
                breakdowns[(row["event"], field)][label or "(unrecognized)"] += 1

            if row["event"] == "hook_signal" and row["valid"]:
                data = row["data"]
                key = (data["hook"], data["rule_id"])
                item = effectiveness.setdefault(key, {
                    "hook": data["hook"], "rule_id": data["rule_id"],
                    "signals": 0, "sessions": set(), "noted": 0, "asked": 0,
                    "blocked": 0, "resolved": 0, "context_chars": 0,
                    "last_seen": "",
                })
                item["signals"] += 1
                if row["session_id"]:
                    item["sessions"].add(row["session_id"])
                item[data["outcome"]] += data["count"]
                item["context_chars"] += data["context_chars"]
                item["last_seen"] = max(item["last_seen"], row["timestamp"])

            if recent.maxlen:
                recent.append({key: row[key] for key in (
                    "id", "timestamp", "project", "event", "agent_type", "agent_id",
                    "tool_use_id", "valid", "data",
                )})
    except (OSError, sqlite3.Error, ValueError) as error:
        return _empty_report(error=str(error))

    report["sessions"] = len(sessions)
    report["agent_instances"] = len(agents)
    report["schema_versions"] = [[key, value] for key, value in sorted(schema_versions.items())]
    report["unknown_events"] = [[key, value] for key, value in unknown.most_common()]
    report["event_counts"] = [[key, value] for key, value in event_counts.most_common()]
    report["by_day"] = [[key, value] for key, value in sorted(days.items())]
    report["by_agent"] = [[key, value] for key, value in by_agent.most_common()]
    report["agent_lifecycle"] = []
    for item in sorted(lifecycle.values(), key=lambda value: value["agent"]):
        item["instances"] = len(item["instances"])
        item["unmatched"] = item["started"] - item["stopped"]
        report["agent_lifecycle"].append(item)
    report["breakdowns"] = [
        {
            "event": event,
            "key": field,
            "total": sum(values.values()),
            "items": [[key, value] for key, value in values.most_common()],
        }
        for (event, field), values in breakdowns.items() if values
    ]
    report["hook_effectiveness"] = []
    for item in effectiveness.values():
        item["sessions"] = len(item["sessions"])
        report["hook_effectiveness"].append(item)
    report["hook_effectiveness"].sort(
        key=lambda item: (-item["signals"], item["hook"], item["rule_id"])
    )
    report["recent_events"] = list(reversed(recent))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(default_db_path()))
    parser.add_argument("--format", choices=("summary", "jsonl"), default="summary")
    parser.add_argument("--after-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.format == "summary":
        report = build_report(args.db)
        print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None))
        return 0 if report["active"] or not report["error"] else 1

    if not Path(args.db).is_file():
        return 0
    try:
        for row in iter_events(args.db, after_id=args.after_id, limit=args.limit):
            print(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"telemetry stream unavailable: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
