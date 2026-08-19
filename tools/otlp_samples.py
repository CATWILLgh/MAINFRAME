#!/usr/bin/env python3
"""Turn OTLP log records into MAINFRAME's allowlisted telemetry payloads.

Everything the harnesses put on the wire passes through here, and only the
explicitly named scalar fields come out. Prompts, tool arguments, tool output,
account identifiers and e-mail addresses are present in every batch and are
never carried into a payload.
"""

from __future__ import annotations

import datetime
import hashlib
import json


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


def attributes(rows):
    result = {}
    for item in rows or []:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        result[item["key"]] = _value(item.get("value"))
    return result


def children(value, camel, snake):
    if not isinstance(value, dict):
        return []
    rows = value.get(camel, value.get(snake, []))
    return rows if isinstance(rows, list) else []


def resolve_event_name(body, attrs, resource):
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


def _record_timestamp(record):
    raw = record.get("timeUnixNano", record.get("time_unix_nano"))
    try:
        nanos = int(raw)
    except (TypeError, ValueError):
        return ""
    if nanos <= 0:
        return ""
    value = datetime.datetime.fromtimestamp(
        nanos / 1_000_000_000, tz=datetime.timezone.utc
    )
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


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


def _tool_result_payload(adapter_id, event_name, attrs, record):
    tool = _text(attrs, "tool_name")
    success = _flag(attrs, "success")
    duration = _present(attrs, "duration_ms")
    if not tool or success is None or duration is None:
        return None
    payload = {
        "sample_id": _sample_id(
            adapter_id, event_name, _text(attrs, "tool_use_id", "call_id"),
            record, {"tool": tool, "success": success},
        ),
        "tool_name": tool, "success": success, "duration_ms": duration,
    }
    # Codex reports no payload sizes; an absent field beats a fabricated zero.
    for field, key in (
        ("input_bytes", "tool_input_size_bytes"),
        ("output_bytes", "tool_result_size_bytes"),
    ):
        value = _present(attrs, key)
        if value is not None:
            payload[field] = value
    return payload


def _tool_decision_payload(adapter_id, event_name, attrs, record):
    tool = _text(attrs, "tool_name")
    # The vocabulary differs per harness ("accept" vs "approved"), so the value
    # is normalized for grouping but never constrained to a closed set.
    decision = _text(attrs, "decision", limit=48).lower()
    if not tool or not decision:
        return None
    payload = {
        "sample_id": _sample_id(
            adapter_id, event_name, _text(attrs, "tool_use_id", "call_id"),
            record, {"tool": tool, "decision": decision},
        ),
        "tool_name": tool, "decision": decision,
    }
    source = _text(attrs, "source", limit=48)
    if source:
        payload["source"] = source
    return payload


def _hook_execution_payload(adapter_id, event_name, attrs, record):
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
    return {
        "sample_id": _sample_id(
            adapter_id, event_name, _text(attrs, "hook_name", limit=64), record,
            {"sequence": attrs.get("event.sequence"), **counts},
        ),
        "hook_event": hook_event, **counts,
    }


# Harness events both adapters share, plus the Claude-only hook channel. Codex
# reports hook health through its own dispatcher instead.
_HARNESS_EVENTS = {
    "tool_result": ("tool_result", _tool_result_payload, None),
    "tool_decision": ("tool_decision", _tool_decision_payload, None),
    "hook_execution_complete": (
        "hook_execution", _hook_execution_payload, "claude-code"),
}


def _harness_sample(adapter_id, event_name, attrs, record):
    """Tool and hook execution facts — names, outcomes and sizes, never content."""
    entry = _HARNESS_EVENTS.get(event_name.split(".", 1)[-1])
    if entry is None:
        return None
    event, build, only_adapter = entry
    if only_adapter is not None and adapter_id != only_adapter:
        return None
    payload = build(adapter_id, event_name, attrs, record)
    if payload is None:
        return None
    sample = {
        "adapter_id": adapter_id, "event": event,
        "session_id": _session_of(adapter_id, attrs),
        "model": _text(attrs, "model"), "payload": payload,
    }
    if event == "tool_decision":
        sample["tool_use_id"] = _text(attrs, "tool_use_id", "call_id")
        sample["timestamp"] = _record_timestamp(record)
    return sample


def samples(adapter_id, event_name, attrs, record):
    usage = _usage_sample(adapter_id, event_name, attrs, record)
    if usage is not None:
        return [usage]
    harness = _harness_sample(adapter_id, event_name, attrs, record)
    return [harness] if harness is not None else []
