"""Privacy-safe event contract for MAINFRAME Codex development telemetry."""

ROW_SCHEMA_VERSION = 1
MAX_TEXT_CHARS = 256

EVENT_FIELDS = {
    "session": {"phase": str, "source": str},
    "user_prompt": {"prompt_len": int},
    "compaction": {"trigger": str},
    "subagent_start": {},
    "subagent_stop": {},
    "permission_request": {"tool_name": str, "permission_mode": str},
    "hook_run": {"status": str, "duration_ms": int, "recipient": str},
    "hook_signal": {
        "hook": str,
        "rule_id": str,
        "outcome": str,
        "count": int,
        "context_chars": int,
    },
}

REQUIRED_FIELDS = {
    "session": {"phase", "source"},
    "user_prompt": {"prompt_len"},
    "compaction": {"trigger"},
    "permission_request": {"tool_name", "permission_mode"},
    "hook_run": {"status", "duration_ms", "recipient"},
    "hook_signal": {"hook", "rule_id", "outcome", "count", "context_chars"},
}

FIELD_VALUES = {
    ("session", "phase"): {"start", "end"},
    ("session", "source"): {"startup", "resume", "clear", "compact", "ended"},
    ("compaction", "trigger"): {"manual", "auto"},
    ("hook_run", "status"): {"completed", "failed"},
    ("hook_run", "recipient"): {"root", "subagent"},
    ("hook_signal", "outcome"): {"noted", "asked", "blocked", "resolved"},
}


def validate_payload(event, payload):
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
        valid = (
            isinstance(value, int) and not isinstance(value, bool)
            if expected is int else isinstance(value, expected)
        )
        if not valid:
            raise ValueError(f"telemetry field {key} must be {expected.__name__}")
        if isinstance(value, str) and (not value or len(value) > MAX_TEXT_CHARS):
            raise ValueError(
                f"telemetry field {key} must contain 1-{MAX_TEXT_CHARS} characters"
            )
        if isinstance(value, int) and value < 0:
            raise ValueError(f"telemetry field {key} cannot be negative")
        accepted = FIELD_VALUES.get((event, key))
        if accepted is not None and value not in accepted:
            raise ValueError(f"telemetry field {key} must be one of {sorted(accepted)}")
        normalized[key] = value
    return normalized
