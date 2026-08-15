"""Small Codex-native compatibility layer for deterministic hook checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys


CODE_EXTENSIONS = frozenset({
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".dart", ".go", ".rb", ".rs", ".java", ".kt", ".kts", ".swift",
    ".cs", ".cpp", ".cc", ".c", ".h", ".hpp", ".scala", ".php",
    ".lua", ".sh", ".bash", ".zsh", ".sql", ".vue", ".svelte",
})

HUB_HOOK_FILES = frozenset({
    "mainframe-hook.py", "scan-suppression-markers.py",
    "stop-gate-suppression-markers.py", "python-security-scan.py",
    "python-security-stop-gate.py", "nodejs-security-scan.py",
    "nodejs-security-stop-gate.py",
    "_bash_patterns.py", "comment-discipline-reminder.py",
    "stop-gate-comment-discipline.py", "comment_extract.py",
    "_comment_findings.py", "_python_findings.py", "_node_findings.py",
    "_length_check.py",
    "length-quality-note.py", "_hooklib.py", "_markers.py",
    "_marker_state.py", "_notice_state.py",
})


def ext(path):
    dot = path.rfind(".")
    slash = max(path.rfind("/"), path.rfind("\\"))
    return path[dot:].lower() if dot > slash else ""


def load_payload():
    try:
        value = json.load(sys.stdin)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def emit_note(event, text):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }
    }))


def emit_permission(decision, reason):
    if decision not in {"allow", "deny"}:
        raise ValueError(f"unsupported Codex PreToolUse decision: {decision}")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    return reason


def emit_block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))
    return reason


def stop_guard_cwd(payload):
    if payload.get("stop_hook_active"):
        return None
    return payload.get("cwd") or "."


def read_git_head(file_path):
    if not file_path:
        return None
    cwd = os.path.dirname(file_path) or "."
    try:
        rel = subprocess.check_output(
            ["git", "ls-files", "--full-name", file_path], cwd=cwd,
            stderr=subprocess.DEVNULL, timeout=2,
        ).decode().strip()
        if not rel:
            return None
        return subprocess.check_output(
            ["git", "show", f"HEAD:{rel}"], cwd=cwd,
            stderr=subprocess.DEVNULL, timeout=2,
        ).decode()
    except Exception:
        return None


def log_hook_signal(*_args, **_kwargs):
    """Telemetry is deliberately absent until the Codex --dev layer exists."""
    return "disabled"


def run(main_fn):
    try:
        main_fn()
    except Exception:
        sys.exit(1)
    sys.exit(0)
