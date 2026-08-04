from __future__ import annotations

from pathlib import Path


SUPPORTED_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PostToolUseFailure",
    "Stop",
)

CORE_EVENT_DETECTORS: dict[str, tuple[str, ...]] = {
    "SessionStart": (
        "session-posture.py",
        "hooklib-smoke-check.py",
        "task-workflow-engagement.py",
        "concise-reminder.py",
    ),
    "PreToolUse": (
        "path-validation.py",
        "secret-commit-gate.py",
        "bash-pattern-reminder.py",
        "commit-conventional-reminder.py",
    ),
    "PostToolUse": (
        "scan-suppression-markers.py",
        "comment-discipline-reminder.py",
        "ticket-id-format-reminder.py",
        "python-security-scan.py",
        "python-deps-audit.py",
        "nodejs-deps-audit.py",
        "nodejs-security-scan.py",
    ),
    "Stop": (
        "stop-gate-suppression-markers.py",
        "stop-gate-comment-discipline.py",
        "python-security-stop-gate.py",
        "nodejs-security-stop-gate.py",
        "frontend-fsd-gate.py",
    ),
}

EVENT_MATCHERS = {
    "SessionStart": "startup|resume|clear|compact",
    "PreToolUse": ".*",
    "PostToolUse": ".*",
    "Stop": ".*",
}

HOOK_TIMEOUT_MS = 65_000


def render_hook_events(bridge_path: Path) -> dict[str, list[dict]]:
    events: dict[str, list[dict]] = {}
    for event in CORE_EVENT_DETECTORS:
        process = {
            "type": "process",
            "command": "python3",
            "args": [str(bridge_path), event],
            "timeoutMs": HOOK_TIMEOUT_MS,
            "statusMessage": f"mainframe:{event}",
        }
        events[event] = [{"matcher": EVENT_MATCHERS[event], "hooks": [process]}]
    return events
