#!/usr/bin/env python3
"""Read adapter-owned MAINFRAME telemetry as validated summaries or JSONL."""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import importlib.util
import math
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_INSTALLED_DB = Path(
    "~/.claude/mainframe/claude-code/telemetry/telemetry.db"
).expanduser()
CODEX_INSTALLED_DB = (
    Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    / "mainframe" / "codex" / "telemetry" / "telemetry.db"
)
CLAUDE_REPOSITORY_DB = (
    ROOT / "workspace" / "runtime" / "claude-code" / "telemetry" / "telemetry.db"
)
CODEX_REPOSITORY_DB = (
    ROOT / "workspace" / "runtime" / "codex" / "telemetry" / "telemetry.db"
)


def _load_contract(adapter_id, path):
    spec = importlib.util.spec_from_file_location(
        "mainframe_telemetry_contract_" + adapter_id.replace("-", "_"), path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {adapter_id} telemetry contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTRACTS = {
    "claude-code": _load_contract(
        "claude-code",
        ROOT / "adapters" / "claude-code" / "plugin" / "hooks" / "scripts"
        / "_telemetry_contract.py",
    ),
    "codex": _load_contract(
        "codex",
        ROOT / "adapters" / "codex" / "hooks" / "scripts"
        / "_telemetry_contract.py",
    ),
}
ADAPTER_LABELS = {"claude-code": "Claude Code", "codex": "Codex"}

BREAKDOWN_FIELDS = {
    "session": ("phase",),
    "compaction": ("trigger",),
    "auto_permission_denied": ("tool_name",),
    "skill_request": ("skill", "invoker"),
    "ticket_change": ("operation",),
    "code_edit": ("lang", "operation"),
    "init_reminder": ("reminded",),
    "model_lab": ("status",),
    "permission_request": ("tool_name", "permission_mode"),
    "hook_run": ("status", "recipient"),
    "tool_decision": ("decision", "source"),
}

# Why a row never reached a metric. "Excluded" alone reads as data loss; naming
# the reason separates an old storage format from a real collection failure.
EXCLUSION_REASONS = (
    "legacy_schema", "invalid_payload", "unknown_event", "other_origin",
)


def _percentile(values, fraction):
    """Nearest-rank percentile; 0 for an empty sample so callers stay total."""
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return int(ordered[min(index, len(ordered) - 1)])


def _duration_summary(values):
    return {
        "samples": len(values),
        "median_ms": _percentile(values, 0.5),
        "p95_ms": _percentile(values, 0.95),
        "max_ms": max(values) if values else 0,
    }

_SESSION_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _effective_origin(origin, session_id):
    """Keep stored provenance honest while recovering old runtime rows."""
    origin = str(origin or "unclassified")
    if origin != "unclassified":
        return origin
    if _SESSION_UUID_RE.fullmatch(str(session_id or "")):
        return "runtime-inferred"
    return origin


def default_db_path(adapter_id="claude-code"):
    installed, repository = {
        "claude-code": (CLAUDE_INSTALLED_DB, CLAUDE_REPOSITORY_DB),
        "codex": (CODEX_INSTALLED_DB, CODEX_REPOSITORY_DB),
    }[adapter_id]
    return installed if installed.is_file() else repository


def default_db_paths():
    return {adapter_id: default_db_path(adapter_id) for adapter_id in CONTRACTS}


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
        selected("turn_id", "''"),
        selected("prompt_id", "''"),
        selected("agent_id", "''"),
        "agent_type",
        selected("tool_use_id", "''"),
        "project",
        selected("hook_event", "''"),
        selected("model", "''"),
        selected("origin", "'unclassified'"),
        "event",
        "payload",
    ))


def iter_events(path, after_id=0, limit=None, adapter_id="claude-code"):
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
            (row_id, timestamp, schema_version, session_id, turn_id, prompt_id,
             agent_id, agent_type, tool_use_id, project, hook_event, model, origin, event,
             raw_payload) = row
            errors = []
            try:
                payload = json.loads(raw_payload or "")
                if not isinstance(payload, dict):
                    raise ValueError("payload is not an object")
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                payload = {}
                errors.append(str(error))

            version = int(schema_version or 1)
            contract = CONTRACTS[adapter_id]
            if not errors and version >= contract.ROW_SCHEMA_VERSION:
                try:
                    payload = contract.validate_payload(str(event), payload)
                except ValueError as error:
                    payload = {}
                    errors.append(str(error))

            effective_origin = _effective_origin(origin, session_id)
            yield {
                "adapter_id": adapter_id,
                "schema_version": version,
                "id": int(row_id),
                "timestamp": str(timestamp or ""),
                "session_id": str(session_id or ""),
                "turn_id": str(turn_id or ""),
                "prompt_id": str(prompt_id or ""),
                "agent_id": str(agent_id or ""),
                "agent_type": str(agent_type or ""),
                "tool_use_id": str(tool_use_id or ""),
                "project": str(project or ""),
                "source_event": str(hook_event or ""),
                "model": str(model or ""),
                "origin": effective_origin,
                "event": str(event or ""),
                "data": payload,
                "valid": not errors,
                "errors": errors,
            }
    finally:
        connection.close()


def _empty_report(
    active=False, error="", included_origins=None, adapter_id="claude-code"
):
    return {
        "adapter_id": adapter_id,
        "adapter_label": ADAPTER_LABELS.get(adapter_id, adapter_id),
        "active": active,
        "format_version": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds").replace("+00:00", "Z"),
        "records": 0,
        "usable_records": 0,
        "excluded_records": 0,
        "sessions": 0,
        "agent_instances": 0,
        "first_timestamp": "",
        "last_timestamp": "",
        "last_id": 0,
        "schema_versions": [],
        "origins": [],
        "included_origins": sorted(included_origins or []),
        "stored_first_timestamp": "",
        "stored_last_timestamp": "",
        "exclusions": {reason: 0 for reason in EXCLUSION_REASONS},
        "tool_reliability": [],
        "tool_decisions": [],
        "hook_health": [],
        "legacy_rows": 0,
        "invalid_rows": 0,
        "invalid_examples": [],
        "unknown_events": [],
        "event_counts": [],
        "by_day": [],
        "by_agent": [],
        "by_model": [],
        "agent_lifecycle": [],
        "breakdowns": [],
        "hook_effectiveness": [],
        "token_usage": {
            "evidence": "unavailable",
            "requests": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "cache_write_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
            # total_tokens counts only freshly billed input plus output, the way
            # the vendor consoles report it. all_tokens adds cache reads and
            # writes — the real volume moved through the model, and normally
            # orders of magnitude larger.
            "total_tokens": 0,
            "all_tokens": 0,
            "by_source": [],
            "by_model": [],
        },
        "cost": {
            "evidence": "unavailable",
            "micro_usd": 0,
            "reporting_requests": 0,
            "total_requests": 0,
            "by_model": [],
        },
        "latency": {"evidence": "unavailable", **_duration_summary([])},
        "harness_context_cost": {
            "evidence": "estimated",
            "characters": 0,
            "estimated_tokens_low": 0,
            "estimated_tokens_high": 0,
            "method": "character-range-2-to-6",
            "causal_overhead": "unproven",
        },
        "recent_events": [],
        "error": error,
    }


def build_report(
    path, recent_limit=40, included_origins=None, adapter_id="claude-code"
):
    """Aggregate the same validated stream consumed by the machine CLI and UI."""
    allowed_origins = set(
        included_origins
        if included_origins is not None
        else {"runtime", "runtime-inferred", "model-lab"}
    )
    path = Path(path)
    if not path.is_file():
        return _empty_report(
            included_origins=allowed_origins, adapter_id=adapter_id
        )

    report = _empty_report(
        active=True, included_origins=allowed_origins, adapter_id=adapter_id
    )
    contract = CONTRACTS[adapter_id]
    sessions = set()
    agents = set()
    schema_versions = collections.Counter()
    origins = collections.Counter()
    event_counts = collections.Counter()
    days = collections.Counter()
    by_agent = collections.Counter()
    by_model = collections.Counter()
    unknown = collections.Counter()
    lifecycle = {}
    breakdowns = {
        (event, field): collections.Counter()
        for event, fields in BREAKDOWN_FIELDS.items() for field in fields
    }
    effectiveness = {}
    usage = collections.Counter()
    usage_by_source = {}
    usage_by_model = {}
    cost_by_model = {}
    request_latencies = []
    tools = {}
    decisions = collections.Counter()
    hook_health = {}
    recent = collections.deque(maxlen=max(0, int(recent_limit)))

    try:
        rows = iter_events(path, adapter_id=adapter_id)
        for row in rows:
            report["records"] += 1
            schema_versions[row["schema_version"]] += 1
            origins[row["origin"]] += 1
            if row["timestamp"]:
                report["stored_first_timestamp"] = (
                    report["stored_first_timestamp"] or row["timestamp"])
                report["stored_last_timestamp"] = row["timestamp"]
            if row["schema_version"] < contract.ROW_SCHEMA_VERSION:
                report["legacy_rows"] += 1
            if row["event"] not in contract.EVENT_FIELDS:
                unknown[row["event"] or "(empty)"] += 1

            if not row["valid"]:
                report["invalid_rows"] += 1
                if len(report["invalid_examples"]) < 10:
                    report["invalid_examples"].append({
                        "id": row["id"], "event": row["event"],
                        "errors": row["errors"],
                    })

            usable = (
                row["schema_version"] >= contract.ROW_SCHEMA_VERSION
                and row["valid"] and row["event"] in contract.EVENT_FIELDS
                and row["origin"] in allowed_origins
            )
            if not usable:
                report["excluded_records"] += 1
                if row["schema_version"] < contract.ROW_SCHEMA_VERSION:
                    report["exclusions"]["legacy_schema"] += 1
                elif row["event"] not in contract.EVENT_FIELDS:
                    # An unknown event also fails validation, so it is classified
                    # first — otherwise every retired event name would be filed
                    # as a corrupt payload.
                    report["exclusions"]["unknown_event"] += 1
                elif not row["valid"]:
                    report["exclusions"]["invalid_payload"] += 1
                else:
                    report["exclusions"]["other_origin"] += 1
                continue
            report["usable_records"] += 1
            report["last_id"] = row["id"]
            report["first_timestamp"] = report["first_timestamp"] or row["timestamp"]
            report["last_timestamp"] = row["timestamp"] or report["last_timestamp"]
            if row["session_id"]:
                sessions.add(row["session_id"])
            if row["agent_id"]:
                agents.add(row["agent_id"])
            event_counts[row["event"]] += 1
            if row["timestamp"]:
                days[row["timestamp"][:10]] += 1
            role = row["agent_type"] or "(main context)"
            by_agent[role] += 1
            if row["model"]:
                by_model[row["model"]] += 1

            # A lifecycle row without an agent identity cannot describe an
            # agent's lifetime; counting it produced stops with no matching start
            # and a permanent phantom gap.
            if (row["event"] in ("subagent_start", "subagent_stop")
                    and (row["agent_id"] or row["agent_type"])):
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

            if row["event"] == "model_usage" and row["valid"]:
                data = row["data"]
                source = data["source"]
                source_usage = usage_by_source.setdefault(source, collections.Counter())
                model = row["model"] or "(unknown)"
                model_usage = usage_by_model.setdefault(model, collections.Counter())
                for source_key, payload_key in (
                    ("requests", "request_count"),
                    ("input_tokens", "input_tokens"),
                    ("cached_input_tokens", "cached_input_tokens"),
                    ("cache_write_tokens", "cache_write_tokens"),
                    ("output_tokens", "output_tokens"),
                    ("reasoning_output_tokens", "reasoning_output_tokens"),
                    ("total_tokens", "total_tokens"),
                ):
                    value = data[payload_key]
                    usage[source_key] += value
                    source_usage[source_key] += value
                    model_usage[source_key] += value
                everything = (
                    data["input_tokens"] + data["cached_input_tokens"]
                    + data["cache_write_tokens"] + data["output_tokens"]
                )
                usage["all_tokens"] += everything
                source_usage["all_tokens"] += everything
                model_usage["all_tokens"] += everything
                # An absent cost field means the source does not publish one, so
                # the reporting request count — not the row count — is the base.
                if "cost_micro_usd" in data:
                    usage["cost_micro_usd"] += data["cost_micro_usd"]
                    usage["cost_requests"] += data["request_count"]
                    bucket = cost_by_model.setdefault(model, collections.Counter())
                    bucket["micro_usd"] += data["cost_micro_usd"]
                    bucket["requests"] += data["request_count"]
                if "duration_ms" in data:
                    request_latencies.append(data["duration_ms"])

            if row["event"] == "tool_result" and row["valid"]:
                data = row["data"]
                item = tools.setdefault(data["tool_name"], {
                    "tool_name": data["tool_name"], "calls": 0, "failures": 0,
                    "durations": [], "output_bytes": 0,
                })
                item["calls"] += 1
                if not data["success"]:
                    item["failures"] += 1
                item["durations"].append(data["duration_ms"])
                item["output_bytes"] += data.get("output_bytes", 0)

            if row["event"] == "tool_decision" and row["valid"]:
                data = row["data"]
                decisions[(
                    data["tool_name"], data["decision"], data.get("source", ""),
                )] += 1

            if row["event"] in ("hook_execution", "hook_run") and row["valid"]:
                data = row["data"]
                key = (
                    data["hook_event"] if row["event"] == "hook_execution"
                    else row["source_event"] or "(unreported)"
                )
                item = hook_health.setdefault(key, {
                    "hook_event": key, "runs": 0, "errors": 0, "blocking": 0,
                    "cancelled": 0, "durations": [],
                })
                if row["event"] == "hook_execution":
                    item["runs"] += data["hooks"]
                    item["errors"] += data["errors"]
                    item["blocking"] += data["blocking"]
                    item["cancelled"] += data["cancelled"]
                else:
                    item["runs"] += 1
                    item["errors"] += int(data["status"] == "failed")
                item["durations"].append(data["duration_ms"])

            if recent.maxlen:
                recent.append({key: row[key] for key in (
                    "id", "timestamp", "project", "event", "agent_type", "agent_id",
                    "tool_use_id", "model", "origin", "valid", "data",
                )})
    except (OSError, sqlite3.Error, ValueError) as error:
        return _empty_report(
            error=str(error), included_origins=allowed_origins, adapter_id=adapter_id
        )

    report["sessions"] = len(sessions)
    report["agent_instances"] = len(agents)
    report["schema_versions"] = [[key, value] for key, value in sorted(schema_versions.items())]
    report["origins"] = [[key, value] for key, value in sorted(origins.items())]
    report["unknown_events"] = [[key, value] for key, value in unknown.most_common()]
    report["event_counts"] = [[key, value] for key, value in event_counts.most_common()]
    report["by_day"] = [[key, value] for key, value in sorted(days.items())]
    report["by_agent"] = [[key, value] for key, value in by_agent.most_common()]
    report["by_model"] = [[key, value] for key, value in by_model.most_common()]
    report["agent_lifecycle"] = []
    for item in sorted(lifecycle.values(), key=lambda value: value["agent"]):
        item["instances"] = len(item["instances"])
        item["missing_start"] = max(0, item["stopped"] - item["started"])
        item["missing_stop"] = max(0, item["started"] - item["stopped"])
        item["unmatched"] = item["missing_start"] + item["missing_stop"]
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
    report["tool_reliability"] = sorted(
        (
            {
                "tool_name": item["tool_name"], "calls": item["calls"],
                "failures": item["failures"],
                "output_bytes": item["output_bytes"],
                **_duration_summary(item["durations"]),
            }
            for item in tools.values()
        ),
        key=lambda item: (-item["calls"], item["tool_name"]),
    )
    report["tool_decisions"] = [
        {"tool_name": tool, "decision": decision, "source": source, "count": count}
        for (tool, decision, source), count in decisions.most_common()
    ]
    report["hook_health"] = sorted(
        (
            {
                "hook_event": item["hook_event"], "runs": item["runs"],
                "errors": item["errors"], "blocking": item["blocking"],
                "cancelled": item["cancelled"],
                **_duration_summary(item["durations"]),
            }
            for item in hook_health.values()
        ),
        key=lambda item: (-item["errors"], -item["runs"], item["hook_event"]),
    )
    report["latency"] = {
        "evidence": "exact" if request_latencies else "unavailable",
        **_duration_summary(request_latencies),
    }
    report["cost"] = {
        "evidence": (
            "unavailable" if not usage["cost_requests"]
            else "exact" if usage["cost_requests"] >= usage["requests"]
            else "partial"
        ),
        "micro_usd": usage["cost_micro_usd"],
        "reporting_requests": usage["cost_requests"],
        "total_requests": usage["requests"],
        "by_model": sorted(
            (
                {
                    "model": model, "micro_usd": values["micro_usd"],
                    "requests": values["requests"],
                }
                for model, values in cost_by_model.items()
            ),
            key=lambda item: -item["micro_usd"],
        ),
    }
    usage_keys = (
        "requests", "input_tokens", "cached_input_tokens", "cache_write_tokens",
        "output_tokens", "reasoning_output_tokens",
        "total_tokens", "all_tokens",
    )
    report["token_usage"] = {
        "evidence": "exact" if usage["requests"] else "unavailable",
        **{key: usage[key] for key in usage_keys},
        "by_source": [
            {"source": source, **{key: values[key] for key in usage_keys}}
            for source, values in sorted(usage_by_source.items())
        ],
        "by_model": [
            {"model": model, **{key: values[key] for key in usage_keys}}
            for model, values in sorted(usage_by_model.items())
        ],
    }
    context_chars = sum(item["context_chars"] for item in effectiveness.values())
    report["harness_context_cost"] = {
        "evidence": "estimated",
        "characters": context_chars,
        "estimated_tokens_low": math.ceil(context_chars / 6),
        "estimated_tokens_high": math.ceil(context_chars / 2),
        "method": "character-range-2-to-6",
        "causal_overhead": "unproven",
    }
    report["recent_events"] = list(reversed(recent))
    return report


def build_multi_report(paths=None, recent_limit=40):
    """Combine adapter summaries without combining their runtime storage."""
    paths = paths or default_db_paths()
    adapters = [
        build_report(path, recent_limit=recent_limit, adapter_id=adapter_id)
        for adapter_id, path in sorted(paths.items())
    ]
    result = _empty_report(adapter_id="all")
    result["adapter_label"] = "All adapters"
    result["format_version"] = 2
    result["adapters"] = adapters
    result["active"] = any(item["active"] for item in adapters)
    for key in (
        "records", "usable_records", "excluded_records", "sessions",
        "agent_instances", "legacy_rows", "invalid_rows",
    ):
        result[key] = sum(item[key] for item in adapters)
    result["exclusions"] = {
        reason: sum(item["exclusions"][reason] for item in adapters)
        for reason in EXCLUSION_REASONS
    }
    result["stored_first_timestamp"] = min(
        (item["stored_first_timestamp"] for item in adapters
         if item["stored_first_timestamp"]), default="")
    result["stored_last_timestamp"] = max(
        (item["stored_last_timestamp"] for item in adapters
         if item["stored_last_timestamp"]), default="")

    counters = {
        "event_counts": collections.Counter(),
        "by_day": collections.Counter(),
        "by_agent": collections.Counter(),
        "by_model": collections.Counter(),
    }
    for item in adapters:
        for key, counter in counters.items():
            counter.update(dict(item[key]))
    result["event_counts"] = [
        [key, value] for key, value in counters["event_counts"].most_common()
    ]
    result["by_day"] = [
        [key, value] for key, value in sorted(counters["by_day"].items())
    ]
    result["by_agent"] = [
        [key, value] for key, value in counters["by_agent"].most_common()
    ]
    result["by_model"] = [
        [key, value] for key, value in counters["by_model"].most_common()
    ]
    usage_keys = (
        "requests", "input_tokens", "cached_input_tokens", "cache_write_tokens",
        "output_tokens", "reasoning_output_tokens",
        "total_tokens", "all_tokens",
    )
    combined_usage = collections.Counter()
    combined_sources = {}
    combined_models = {}
    for item in adapters:
        for key in usage_keys:
            combined_usage[key] += item["token_usage"][key]
        for source in item["token_usage"]["by_source"]:
            bucket = combined_sources.setdefault(
                (item["adapter_id"], source["source"]), collections.Counter()
            )
            for key in usage_keys:
                bucket[key] += source[key]
        for model in item["token_usage"]["by_model"]:
            bucket = combined_models.setdefault(
                (item["adapter_id"], model["model"]), collections.Counter()
            )
            for key in usage_keys:
                bucket[key] += model[key]
    result["token_usage"] = {
        "evidence": "exact" if combined_usage["requests"] else "unavailable",
        **{key: combined_usage[key] for key in usage_keys},
        "by_source": [
            {
                "adapter_id": adapter_id,
                "source": source,
                **{key: values[key] for key in usage_keys},
            }
            for (adapter_id, source), values in sorted(combined_sources.items())
        ],
        "by_model": [
            {
                "adapter_id": adapter_id,
                "model": model,
                **{key: values[key] for key in usage_keys},
            }
            for (adapter_id, model), values in sorted(combined_models.items())
        ],
    }
    context_chars = sum(
        item["harness_context_cost"]["characters"] for item in adapters
    )
    result["harness_context_cost"] = {
        "evidence": "estimated",
        "characters": context_chars,
        "estimated_tokens_low": math.ceil(context_chars / 6),
        "estimated_tokens_high": math.ceil(context_chars / 2),
        "method": "character-range-2-to-6",
        "causal_overhead": "unproven",
    }

    cost_reporting = sum(item["cost"]["reporting_requests"] for item in adapters)
    result["cost"] = {
        "evidence": (
            "unavailable" if not cost_reporting
            else "exact" if cost_reporting >= combined_usage["requests"]
            else "partial"
        ),
        "micro_usd": sum(item["cost"]["micro_usd"] for item in adapters),
        "reporting_requests": cost_reporting,
        "total_requests": combined_usage["requests"],
        "by_model": [
            {**row, "adapter_id": item["adapter_id"]}
            for item in adapters for row in item["cost"]["by_model"]
        ],
    }
    # Latency percentiles cannot be averaged across adapters, so the combined
    # view keeps each adapter's own summary instead of inventing a merged one.
    result["latency"] = {
        "evidence": "per-adapter",
        "by_adapter": [
            {"adapter_id": item["adapter_id"], **item["latency"]}
            for item in adapters if item["latency"]["samples"]
        ],
        **_duration_summary([]),
    }
    for key in (
        "agent_lifecycle", "breakdowns", "hook_effectiveness",
        "tool_reliability", "tool_decisions", "hook_health",
    ):
        result[key] = []
        for item in adapters:
            result[key].extend([
                {**row, "adapter_id": item["adapter_id"]} for row in item[key]
            ])
    recent = []
    for item in adapters:
        recent.extend([
            {**row, "adapter_id": item["adapter_id"]}
            for row in item["recent_events"]
        ])
    result["recent_events"] = sorted(
        recent, key=lambda row: (row.get("timestamp", ""), row.get("id", 0)),
        reverse=True,
    )[:max(0, int(recent_limit))]
    result["first_timestamp"] = min(
        (item["first_timestamp"] for item in adapters if item["first_timestamp"]),
        default="",
    )
    result["last_timestamp"] = max(
        (item["last_timestamp"] for item in adapters if item["last_timestamp"]),
        default="",
    )
    result["invalid_examples"] = [
        {**row, "adapter_id": item["adapter_id"]}
        for item in adapters for row in item["invalid_examples"]
    ][:10]
    result["unknown_events"] = [
        [f"{item['adapter_id']}:{name}", count]
        for item in adapters for name, count in item["unknown_events"]
    ]
    result["error"] = "; ".join(
        f"{item['adapter_id']}: {item['error']}" for item in adapters if item["error"]
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None)
    parser.add_argument("--adapter", choices=tuple(CONTRACTS), default="claude-code")
    parser.add_argument("--all", action="store_true", help="read every adapter-owned DB")
    parser.add_argument("--format", choices=("summary", "jsonl"), default="summary")
    parser.add_argument("--after-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.format == "summary":
        report = (
            build_multi_report()
            if args.all or args.db is None
            else build_report(args.db, adapter_id=args.adapter)
        )
        print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None))
        return 0 if report["active"] or not report["error"] else 1

    db = args.db or str(default_db_path(args.adapter))
    if not Path(db).is_file():
        return 0
    try:
        for row in iter_events(
            db, after_id=args.after_id, limit=args.limit, adapter_id=args.adapter
        ):
            print(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"telemetry stream unavailable: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
