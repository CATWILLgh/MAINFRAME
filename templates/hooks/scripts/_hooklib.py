"""Reference hook IO; replace payload/output bindings for the target product."""

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

def ext(path):
    dot = path.rfind(".")
    slash = max(path.rfind("/"), path.rfind("\\"))
    return path[dot:].lower() if dot > slash else ""

def emit_note(event, text):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }
    }))

def emit_permission(decision, reason):
    if decision not in {"allow", "deny"}:
        raise ValueError(f"unsupported reference permission decision: {decision}")
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

HUB_HOOK_FILES = frozenset(name for name in os.listdir(os.path.dirname(__file__)) if name.endswith(".py"))

def load_payload():
    value = json.load(sys.stdin)
    if not isinstance(value, dict):
        raise ValueError("hook payload must be an object")
    return value


def run(main_fn):
    try:
        main_fn()
    except Exception as exc:
        print("Hook check unavailable: " + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
