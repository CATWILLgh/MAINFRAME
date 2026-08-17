"""Canonical privacy-safe event contract for MAINFRAME Claude dev telemetry."""

ROW_SCHEMA_VERSION = 2
MAX_TEXT_CHARS = 256

# Every stored payload is a flat mapping of explicitly approved scalar fields.
# Correlation identifiers belong to event columns, not to this free-form area.
EVENT_FIELDS = {
    "session": {"phase": str, "source": str, "end_reason": str},
    "user_prompt": {"prompt_len": int},
    "compaction": {"trigger": str},
    "subagent_start": {},
    "subagent_stop": {},
    "auto_permission_denied": {"tool_name": str},
    "skill_request": {"skill": str, "invoker": str},
    "ticket_change": {"uid": str, "operation": str},
    "code_edit": {
        "lang": str,
        "ext": str,
        "operation": str,
        "duration_ms": int,
    },
    "hook_signal": {
        "hook": str,
        "rule_id": str,
        "outcome": str,
        "count": int,
        "context_chars": int,
    },
    "init_reminder_activated": {},
    "init_reminder": {"turn": int, "reminded": bool, "every": int},
    "model_lab": {
        "provider": str,
        "model": str,
        "effort": str,
        "task": str,
        "status": str,
        "elapsed_bucket_s": int,
    },
    "model_usage": {
        "sample_id": str,
        "source": str,
        "input_tokens": int,
        "cached_input_tokens": int,
        "cache_write_tokens": int,
        "output_tokens": int,
        "reasoning_output_tokens": int,
        "total_tokens": int,
        "request_count": int,
        # Optional: only a source that reports exact billing carries them, so an
        # absent field means "not reported", never "zero".
        "cost_micro_usd": int,
        "duration_ms": int,
    },
    # Native harness signals. They describe the harness's own execution, never
    # tool arguments, results, prompts, or paths.
    "tool_result": {
        "sample_id": str,
        "tool_name": str,
        "success": bool,
        "duration_ms": int,
        "input_bytes": int,
        "output_bytes": int,
    },
    "tool_decision": {
        "sample_id": str, "tool_name": str, "decision": str, "source": str,
    },
    "hook_execution": {
        "sample_id": str,
        "hook_event": str,
        "hooks": int,
        "succeeded": int,
        "blocking": int,
        "errors": int,
        "cancelled": int,
        "duration_ms": int,
    },
}

REQUIRED_FIELDS = {
    "session": {"phase"},
    "user_prompt": {"prompt_len"},
    "compaction": {"trigger"},
    "auto_permission_denied": {"tool_name"},
    "skill_request": {"skill", "invoker"},
    "ticket_change": {"uid", "operation"},
    "code_edit": {"lang", "ext", "operation"},
    "hook_signal": {"hook", "rule_id", "outcome", "count", "context_chars"},
    "init_reminder": {"turn", "reminded", "every"},
    "model_lab": {"provider", "model", "effort", "task", "status", "elapsed_bucket_s"},
    "model_usage": {
        "sample_id", "source", "input_tokens", "cached_input_tokens", "cache_write_tokens",
        "output_tokens", "reasoning_output_tokens", "total_tokens", "request_count",
    },
    "tool_result": {"sample_id", "tool_name", "success", "duration_ms"},
    "tool_decision": {"sample_id", "tool_name", "decision"},
    "hook_execution": {
        "sample_id", "hook_event", "hooks", "succeeded", "blocking",
        "errors", "cancelled", "duration_ms",
    },
}

FIELD_VALUES = {
    ("session", "phase"): {"start", "end"},
    ("session", "source"): {"startup", "resume", "clear", "compact", "fork"},
    ("session", "end_reason"): {
        "clear", "resume", "logout", "prompt_input_exit",
        "bypass_permissions_disabled", "other",
    },
    ("compaction", "trigger"): {"manual", "auto"},
    ("skill_request", "invoker"): {"model", "user"},
    ("ticket_change", "operation"): {"edit", "write", "multiedit"},
    ("code_edit", "lang"): {"frontend", "ts", "python"},
    ("code_edit", "operation"): {"edit", "write", "multiedit"},
    ("hook_signal", "outcome"): {"noted", "asked", "blocked", "resolved"},
    ("model_lab", "status"): {"completed", "deduplicated", "invalid", "unavailable"},
    ("model_usage", "source"): {
        "native-otel", "native-app-server", "transcript", "model-lab",
    },
}


def validate_payload(event, payload):
    """Return a normalized payload or raise ValueError on schema/privacy drift."""
    if event not in EVENT_FIELDS:
        raise ValueError(f"unknown telemetry event: {event}")
    if not isinstance(payload, dict):
        raise ValueError("telemetry payload must be a mapping")

    allowed = EVENT_FIELDS[event]
    extra = set(payload) - set(allowed)
    missing = REQUIRED_FIELDS.get(event, set()) - set(payload)
    if extra:
        raise ValueError(f"unsupported telemetry fields: {sorted(extra)}")
    if missing:
        raise ValueError(f"missing telemetry fields: {sorted(missing)}")

    normalized = {}
    for key, value in payload.items():
        expected = allowed[key]
        # bool is an int subclass; keep the two contracts distinct.
        if expected is int:
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, expected)
        if not valid:
            raise ValueError(f"telemetry field {key} must be {expected.__name__}")
        if isinstance(value, str):
            if not value or len(value) > MAX_TEXT_CHARS:
                raise ValueError(
                    f"telemetry field {key} must contain 1-{MAX_TEXT_CHARS} characters"
                )
        if isinstance(value, int) and value < 0:
            raise ValueError(f"telemetry field {key} cannot be negative")
        accepted = FIELD_VALUES.get((event, key))
        if accepted is not None and value not in accepted:
            raise ValueError(
                f"telemetry field {key} must be one of {sorted(accepted)}"
            )
        normalized[key] = value

    if event == "session":
        phase = normalized["phase"]
        expected = "source" if phase == "start" else "end_reason"
        forbidden = "end_reason" if phase == "start" else "source"
        if expected not in normalized or forbidden in normalized:
            raise ValueError(f"session {phase} requires only {expected}")
    if event == "model_usage" and normalized["request_count"] <= 0:
        raise ValueError("model_usage request_count must be positive")
    return normalized
