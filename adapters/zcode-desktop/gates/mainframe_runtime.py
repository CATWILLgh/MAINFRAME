from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_EVENTS = frozenset({
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PostToolUseFailure",
    "Stop",
})
PERMISSION_STRENGTH = {"allow": 0, "ask": 1, "deny": 2}


class BridgeInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BridgeResult:
    output: dict[str, Any] | None
    exit_code: int
    diagnostics: tuple[str, ...] = ()
    block_reason: str | None = None


@dataclass(frozen=True, slots=True)
class DetectorResult:
    name: str
    output: dict[str, Any] | None
    exit_code: int
    degradation: str | None = None


def _optional_alias(payload: dict[str, Any], target: str, sources: tuple[str, ...], expected: type) -> None:
    for source in sources:
        if source not in payload:
            continue
        value = payload[source]
        if not isinstance(value, expected):
            raise BridgeInputError(f"{source} must be {expected.__name__}")
        payload[target] = value
        return


def normalize_payload(event: str, raw_payload: dict[str, Any]) -> dict[str, Any]:
    if event not in SUPPORTED_EVENTS:
        raise BridgeInputError(f"unsupported hook event: {event}")
    if not isinstance(raw_payload, dict):
        raise BridgeInputError("hook payload must be a JSON object")
    payload = dict(raw_payload)
    for key in ("hookEventName", "hook_event_name"):
        if key in payload and payload[key] != event:
            raise BridgeInputError(f"{key} does not match configured event")
    payload["hook_event_name"] = event
    _optional_alias(payload, "session_id", ("sessionId", "session_id"), str)
    _optional_alias(payload, "tool_name", ("toolName", "tool_name"), str)
    _optional_alias(payload, "tool_input", ("toolInput", "tool_input"), dict)
    _optional_alias(payload, "tool_use_id", ("toolCallId", "tool_use_id"), str)
    _optional_alias(payload, "stop_hook_active", ("stopHookActive", "stop_hook_active"), bool)
    if "cwd" in payload and not isinstance(payload["cwd"], str):
        raise BridgeInputError("cwd must be str")
    if "project_dir" in payload and not isinstance(payload["project_dir"], str):
        raise BridgeInputError("project_dir must be str")
    if "project_dir" not in payload and isinstance(payload.get("cwd"), str):
        payload["project_dir"] = payload["cwd"]
    return payload


def _decode_detector_output(name: str, stdout: bytes, event: str) -> tuple[dict[str, Any] | None, str | None]:
    if not stdout.strip():
        return None, None
    try:
        parsed = json.loads(stdout)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, f"{name}: malformed detector output"
    if not isinstance(parsed, dict):
        return None, f"{name}: detector output must be an object"
    specific = parsed.get("hookSpecificOutput")
    if specific is not None:
        if not isinstance(specific, dict):
            return None, f"{name}: hookSpecificOutput must be an object"
        if specific.get("hookEventName") != event:
            return None, f"{name}: detector returned the wrong event"
    return parsed, None


def _run_detector(
    name: str,
    detector_dir: Path,
    payload_bytes: bytes,
    event: str,
    timeout_seconds: float,
    max_output_bytes: int,
    environment: dict[str, str],
) -> DetectorResult:
    if Path(name).name != name:
        return DetectorResult(name, None, 1, f"{name}: invalid detector name")
    script = detector_dir / name
    if not script.is_file():
        return DetectorResult(name, None, 1, f"{name}: detector is missing")
    try:
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            completed = subprocess.run(
                [sys.executable, str(script)],
                input=payload_bytes,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=timeout_seconds,
                check=False,
                env=environment,
            )
            stdout_size = stdout_file.tell()
            stderr_size = stderr_file.tell()
            stdout_file.seek(0)
            stdout = stdout_file.read(max_output_bytes + 1)
    except subprocess.TimeoutExpired:
        return DetectorResult(name, None, 1, f"{name}: detector timed out")
    if stdout_size > max_output_bytes or stderr_size > max_output_bytes:
        return DetectorResult(name, None, 1, f"{name}: detector output exceeded the limit")
    output, malformed = _decode_detector_output(name, stdout, event)
    if completed.returncode == 2:
        return DetectorResult(name, output, 2, malformed)
    if completed.returncode != 0:
        return DetectorResult(name, None, completed.returncode, f"{name}: detector failed")
    return DetectorResult(name, output, 0, malformed)


def _context_and_verdict(result: DetectorResult) -> tuple[list[str], str | None, str | None, bool]:
    contexts: list[str] = []
    decision = reason = None
    blocked = result.exit_code == 2
    output = result.output or {}
    for key in ("additionalContext", "additional_context", "systemMessage"):
        if isinstance(output.get(key), str) and output[key]:
            contexts.append(output[key])
    specific = output.get("hookSpecificOutput")
    if isinstance(specific, dict):
        context = specific.get("additionalContext")
        if isinstance(context, str) and context:
            contexts.append(context)
        candidate = specific.get("permissionDecision")
        if candidate in PERMISSION_STRENGTH:
            decision = candidate
            raw_reason = specific.get("permissionDecisionReason")
            reason = raw_reason if isinstance(raw_reason, str) else None
    if output.get("decision") == "block":
        blocked = True
        raw_reason = output.get("reason")
        reason = raw_reason if isinstance(raw_reason, str) else reason
    return contexts, decision, reason, blocked


def _compose_output(event: str, results: list[DetectorResult]) -> BridgeResult:
    contexts: list[str] = []
    diagnostics = [item.degradation for item in results if item.degradation]
    decisions: list[tuple[str, str | None]] = []
    block_reasons: list[str] = []
    exit_two = False
    for result in results:
        notes, decision, reason, blocked = _context_and_verdict(result)
        contexts.extend(notes)
        if decision:
            decisions.append((decision, reason))
        if blocked:
            block_reasons.append(reason or f"{result.name} blocked the event")
        if result.exit_code == 2:
            exit_two = True
    contexts.extend(f"MAINFRAME hook bridge degraded: {note}" for note in diagnostics)
    if event == "Stop" and block_reasons:
        output: dict[str, Any] = {"decision": "block", "reason": "\n\n".join(block_reasons)}
        if contexts:
            output["systemMessage"] = "\n\n".join(contexts)
        return BridgeResult(output, 2 if exit_two else 0, tuple(diagnostics), output["reason"])
    strongest = max(decisions, key=lambda item: PERMISSION_STRENGTH[item[0]]) if decisions else None
    if exit_two and event == "PreToolUse":
        strongest = ("deny", "\n\n".join(block_reasons))
    if strongest or contexts:
        specific: dict[str, Any] = {"hookEventName": event}
        if strongest and event == "PreToolUse":
            specific["permissionDecision"] = strongest[0]
            if strongest[1]:
                specific["permissionDecisionReason"] = strongest[1]
        if contexts:
            specific["additionalContext"] = "\n\n".join(contexts)
        output = {"hookSpecificOutput": specific}
    else:
        output = None
    if exit_two:
        reason = "\n\n".join(block_reasons)
        return BridgeResult(output, 2, tuple(diagnostics), reason)
    return BridgeResult(output, 0, tuple(diagnostics))


def run_detectors(
    event: str,
    payload: dict[str, Any],
    detector_names: list[str] | tuple[str, ...],
    detector_dir: Path,
    *,
    timeout_seconds: float,
    max_output_bytes: int,
) -> BridgeResult:
    payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    environment = os.environ.copy()
    project_dir = payload.get("project_dir")
    if isinstance(project_dir, str):
        environment["CLAUDE_PROJECT_DIR"] = project_dir
        environment["ZCODE_PROJECT_DIR"] = project_dir
    results = [
        _run_detector(
            name, detector_dir, payload_bytes, event,
            timeout_seconds, max_output_bytes, environment,
        )
        for name in detector_names
    ]
    return _compose_output(event, results)
