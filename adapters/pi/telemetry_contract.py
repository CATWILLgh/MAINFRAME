"""Privacy-safe event contract for MAINFRAME Pi development telemetry."""

ROW_SCHEMA_VERSION = 1
MAX_TEXT_CHARS = 256

EVENT_FIELDS = {
    "model_usage": {
        "sample_id": str, "source": str, "input_tokens": int,
        "cached_input_tokens": int, "cache_write_tokens": int,
        "output_tokens": int, "reasoning_output_tokens": int,
        "total_tokens": int, "request_count": int, "cost_micro_usd": int,
    },
    "engineer_tool_summary": {
        "sample_id": str, "stage": str, "tool_name": str, "calls": int,
    },
    "engineer_run": {
        "sample_id": str, "mode": str, "status": str, "rounds": int,
        "correction_rounds": int, "checks_total": int, "checks_passed": int,
        "verifier_status": str, "duration_ms": int, "tool_calls": int,
        "repeated_tool_calls": int, "failed_tool_calls": int,
        "compactions": int, "retries": int, "executor_effort": str,
        "verifier_effort": str,
    },
}

REQUIRED_FIELDS = {event: set(fields) for event, fields in EVENT_FIELDS.items()}

FIELD_VALUES = {
    ("model_usage", "source"): {"pi-sdk"},
    ("engineer_tool_summary", "stage"): {"executor", "verifier"},
    ("engineer_run", "mode"): {"new", "resume"},
    ("engineer_run", "status"): {
        "ready-for-architect-review", "blocked", "plan-conflict", "incomplete",
    },
    ("engineer_run", "verifier_status"): {
        "ready-for-architect-review", "correction-required", "blocked",
        "plan-conflict", "unavailable",
    },
    ("engineer_run", "executor_effort"): {
        "off", "minimal", "low", "medium", "high", "xhigh", "max",
    },
    ("engineer_run", "verifier_effort"): {
        "off", "minimal", "low", "medium", "high", "xhigh", "max",
    },
}


def validate_payload(event, payload):
    if event not in EVENT_FIELDS:
        raise ValueError(f"unknown telemetry event: {event}")
    if not isinstance(payload, dict):
        raise ValueError("telemetry payload must be a mapping")
    allowed = EVENT_FIELDS[event]
    extra = set(payload) - set(allowed)
    missing = REQUIRED_FIELDS[event] - set(payload)
    if extra:
        raise ValueError(f"unsupported telemetry fields: {sorted(extra)}")
    if missing:
        raise ValueError(f"missing telemetry fields: {sorted(missing)}")
    normalized = {}
    for key, value in payload.items():
        expected = allowed[key]
        valid = (
            isinstance(value, int) and not isinstance(value, bool)
            if expected is int else isinstance(value, expected)
        )
        if not valid:
            raise ValueError(f"telemetry field {key} must be {expected.__name__}")
        if isinstance(value, str) and (not value or len(value) > MAX_TEXT_CHARS):
            raise ValueError(f"telemetry field {key} must contain 1-{MAX_TEXT_CHARS} characters")
        if isinstance(value, int) and value < 0:
            raise ValueError(f"telemetry field {key} cannot be negative")
        accepted = FIELD_VALUES.get((event, key))
        if accepted is not None and value not in accepted:
            raise ValueError(f"telemetry field {key} must be one of {sorted(accepted)}")
        normalized[key] = value
    if event == "model_usage" and normalized["request_count"] <= 0:
        raise ValueError("model_usage request_count must be positive")
    return normalized
