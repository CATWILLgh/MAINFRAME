#!/usr/bin/env python3
"""Restrict researcher reads to its method and its own WebFetch outputs."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


SKILL_ROOT = Path.home() / ".claude" / "skills" / "mainframe" / "skills" / "research-method"
STATE_ROOT = Path(os.environ.get("TMPDIR", "/tmp")) / "mainframe-researcher-fetches"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
PROFILE_GATED_TOOLS = {
    "WebSearch",
    "mcp__plugin_context7_context7__resolve-library-id",
    "mcp__plugin_context7_context7__query-docs",
}


def decision(kind: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": kind,
            "permissionDecisionReason": reason,
        }
    }


def identity(payload: dict) -> tuple[str, str]:
    session_id = payload.get("session_id")
    agent_id = payload.get("agent_id")
    if not isinstance(session_id, str) or not SAFE_ID.fullmatch(session_id):
        raise ValueError("invalid session id")
    if not isinstance(agent_id, str) or not SAFE_ID.fullmatch(agent_id):
        raise ValueError("invalid agent id")
    return session_id, agent_id


def state_file(payload: dict, kind: str) -> Path:
    session_id, agent_id = identity(payload)
    return STATE_ROOT / f"{session_id}--{agent_id}.{kind}"


def append_state(payload: dict, kind: str, value: str) -> None:
    target = state_file(payload, kind)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(f"{value}\n")
    target.chmod(0o600)


def has_state(payload: dict, kind: str) -> bool:
    state = state_file(payload, kind)
    return state.is_file() and bool(state.read_text(encoding="utf-8").splitlines())


def is_prepared(payload: dict) -> bool:
    return has_state(payload, "method") and has_state(payload, "profiles")


def record_webfetch(payload: dict) -> bool:
    if payload.get("tool_name") != "WebFetch":
        return False
    if not is_prepared(payload):
        return False
    tool_use_id = payload.get("tool_use_id")
    if not isinstance(tool_use_id, str) or not SAFE_ID.fullmatch(tool_use_id):
        return False
    append_state(payload, "fetches", tool_use_id)
    return True


def is_recorded_fetch_output(payload: dict, requested: Path) -> bool:
    session_id, _ = identity(payload)
    relative = requested.relative_to((Path.home() / ".claude" / "projects").resolve(strict=True))
    if len(relative.parts) != 4:
        return False
    _, path_session_id, directory, filename = relative.parts
    if path_session_id != session_id or directory != "tool-results":
        return False
    if not filename.endswith(".txt"):
        return False
    tool_use_id = filename[:-4]
    if not SAFE_ID.fullmatch(tool_use_id):
        return False
    allowed_ids = set(state_file(payload, "fetches").read_text(encoding="utf-8").splitlines())
    return tool_use_id in allowed_ids


def guard_read(payload: dict) -> bool:
    if payload.get("tool_name") != "Read":
        return False
    raw_path = payload.get("tool_input", {}).get("file_path")
    if not isinstance(raw_path, str) or not raw_path:
        return False

    requested = Path(os.path.expanduser(raw_path)).resolve(strict=True)
    root = SKILL_ROOT.resolve(strict=True)
    if os.path.commonpath((str(root), str(requested))) == str(root):
        if requested == root / "SKILL.md":
            append_state(payload, "method", "SKILL.md")
        references = (root / "references").resolve(strict=True)
        if os.path.commonpath((str(references), str(requested))) == str(references):
            append_state(payload, "profiles", requested.relative_to(references).as_posix())
        return True
    try:
        return is_recorded_fetch_output(payload, requested)
    except (OSError, ValueError):
        return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        mode = sys.argv[1] if len(sys.argv) == 2 else ""
        if mode == "record-webfetch":
            allowed = record_webfetch(payload)
            reason = "WebFetch registered" if allowed else "Read every applicable research profile before external research."
        elif mode == "require-profile":
            allowed = payload.get("tool_name") in PROFILE_GATED_TOOLS and is_prepared(payload)
            reason = "Research method and profile loaded" if allowed else "Read research-method/SKILL.md and every applicable research profile before external research."
        elif mode == "guard-read":
            allowed = guard_read(payload)
            reason = "Researcher private input" if allowed else "The researcher may read only its research-method skill directory and its own WebFetch outputs."
        else:
            allowed = False
            reason = "Unknown research guard mode"
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        allowed = False
        reason = "Research guard could not validate this operation."

    if allowed:
        result = decision("allow", reason)
    else:
        result = decision("deny", reason)
    json.dump(result, sys.stdout, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
