#!/usr/bin/env python3
"""Keep primary-session skills out of subagent contexts."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import log_hook_signal, run
except Exception:
    sys.exit(0)


PRIMARY_SESSION_SKILLS = frozenset({"mainframe:infrastructure", "infrastructure"})


def _requested_skill(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    raw = (
        tool_input.get("skill")
        or tool_input.get("name")
        or tool_input.get("command")
        or ""
    )
    return str(raw).strip().split(maxsplit=1)[0] if raw else ""


def authority_decision(payload: dict) -> tuple[str | None, str | None]:
    if payload.get("tool_name") != "Skill" or not payload.get("agent_id"):
        return None, None
    if _requested_skill(payload) not in PRIMARY_SESSION_SKILLS:
        return None, None
    return "deny", (
        "Infrastructure operations belong to the primary session. Return the "
        "infrastructure need and any verified facts to your immediate caller "
        "without loading this skill."
    )


def main() -> None:
    payload = json.load(sys.stdin)
    decision, reason = authority_decision(payload)
    if not decision:
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    log_hook_signal(
        __file__, "primary-session-skill", "blocked", 1, payload,
        context=reason,
    )


if __name__ == "__main__":
    run(main)
