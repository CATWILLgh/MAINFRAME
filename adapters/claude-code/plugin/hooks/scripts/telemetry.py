#!/usr/bin/env python3
"""Passive telemetry hook — silently records Bucket-1 behaviour facts.

Registered on several events (see `adapters/claude-code/plugin/hooks/hooks.json`); branches on
`hook_event_name`, writes one metadata row via `_hooklib.log_event`, and emits
NOTHING to stdout, so it is invisible to the agent. The adapter installer
initializes the SQLite sink once; bounded retry absorbs brief writer contention.
A persistent sink failure exits nonzero so the common launcher can report it
once. Privacy: only typed low-risk metadata is extracted — never prompt text,
file contents, denial reasons, tool arguments, or paths.
"""

import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import initialize_telemetry_db, load_payload, log_event, run
except Exception:
    sys.exit(0)

_TICKET_RE = re.compile(r"[/\\]docs[/\\]tickets[/\\].+\.md$")

# Coarse domain buckets for code edits — only languages a profile sub-agent owns are
# kept; everything else returns None and is not logged, so `code_edit` stays a clean
# denominator for measuring profile-agent use.
_EXT_LANG = {
    ".tsx": "frontend", ".jsx": "frontend",
    ".css": "frontend", ".scss": "frontend", ".sass": "frontend", ".less": "frontend",
    ".vue": "frontend", ".svelte": "frontend",
    ".ts": "ts",
    ".py": "python",
}


def _ticket_uid(file_path):
    # Hash of the ticket's basename — lets DISTINCT tickets be counted without logging
    # the descriptive slug or the path (privacy). Rewrites of the same file share the
    # uid, so create-vs-rewrite is separable in analysis.
    base = os.path.basename(file_path)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]


def _norm_skill(raw):
    # Strip the plugin namespace (`mainframe:init` -> `init`) so the
    # same skill aggregates into one bucket regardless of how it was invoked.
    name = str(raw).split()[0] if raw else ""
    return name.split(":")[-1]


def _lang_bucket(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    return _EXT_LANG.get(ext)


def _record(event, data, payload):
    result = log_event(event, data, payload)
    if result not in ("written", "disabled"):
        raise RuntimeError("telemetry sink unavailable")


def main():
    payload = load_payload()
    event = payload.get("hook_event_name") or ""
    tool_input = payload.get("tool_input") or {}

    if event == "PermissionDenied":
        if not payload.get("tool_use_id") or not payload.get("tool_name"):
            raise RuntimeError("PermissionDenied payload lacks tool identity")
        _record("auto_permission_denied", {"tool_name": payload["tool_name"]}, payload)
    elif event == "SubagentStart":
        if not payload.get("agent_id") or not payload.get("agent_type"):
            raise RuntimeError("SubagentStart payload lacks agent identity")
        _record("subagent_start", {}, payload)
    elif event == "SubagentStop":
        if not payload.get("agent_id") or not payload.get("agent_type"):
            raise RuntimeError("SubagentStop payload lacks agent identity")
        _record("subagent_stop", {}, payload)
    elif event == "UserPromptExpansion":
        command = str(payload.get("command_name") or "")
        if (
            payload.get("expansion_type") != "slash_command"
            or payload.get("command_source") != "plugin"
            or not command.startswith("mainframe:")
        ):
            raise RuntimeError("UserPromptExpansion payload is not a MAINFRAME command")
        _record("skill_request", {
            "skill": _norm_skill(command), "invoker": "user",
        }, payload)
    elif event == "PreToolUse":
        tool = payload.get("tool_name") or ""
        if tool == "Skill":
            skill = tool_input.get("skill") or tool_input.get("name") or tool_input.get("command") or ""
            skill = _norm_skill(skill)
            if not skill:
                raise RuntimeError("Skill payload has no skill name")
            _record("skill_request", {"skill": skill, "invoker": "model"}, payload)
    elif event == "PostToolUse":
        file_path = tool_input.get("file_path") or ""
        if file_path and _TICKET_RE.search(file_path):
            _record("ticket_change", {
                "uid": _ticket_uid(file_path),
                "operation": (payload.get("tool_name") or "unknown").lower(),
            }, payload)
        lang = _lang_bucket(file_path) if file_path else None
        if lang:
            data = {
                "lang": lang,
                "ext": os.path.splitext(file_path)[1].lower(),
                "operation": (payload.get("tool_name") or "unknown").lower(),
            }
            duration = payload.get("duration_ms")
            if isinstance(duration, int) and not isinstance(duration, bool) and duration >= 0:
                data["duration_ms"] = duration
            _record("code_edit", data, payload)
    elif event == "UserPromptSubmit":
        _record("user_prompt", {"prompt_len": len(payload.get("prompt") or "")}, payload)
    elif event == "SessionStart":
        if not payload.get("source"):
            raise RuntimeError("SessionStart payload has no source")
        _record("session", {"phase": "start", "source": payload["source"]}, payload)
    elif event == "SessionEnd":
        if not payload.get("reason"):
            raise RuntimeError("SessionEnd payload has no reason")
        _record("session", {"phase": "end", "end_reason": payload["reason"]}, payload)
    elif event == "PostCompact":
        if payload.get("trigger") not in ("manual", "auto"):
            raise RuntimeError("PostCompact payload has invalid trigger")
        _record("compaction", {"trigger": payload["trigger"]}, payload)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--initialize":
        try:
            initialize_telemetry_db(sys.argv[2])
        except Exception:
            sys.exit(1)
        sys.exit(0)
    run(main)
