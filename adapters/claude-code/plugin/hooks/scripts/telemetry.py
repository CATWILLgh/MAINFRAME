#!/usr/bin/env python3
"""Passive telemetry hook — silently records Bucket-1 behaviour facts.

Registered on several events (see `adapters/claude-code/plugin/hooks/hooks.json`); branches on
`hook_event_name`, writes one metadata row via `_hooklib.log_event`, and emits
NOTHING to stdout, so it is invisible to the agent. The adapter installer
initializes the SQLite sink once; bounded retry absorbs brief writer contention.
A persistent sink failure exits nonzero so the common launcher can report it
once. Privacy: only low-risk metadata is extracted — never
`tool_input` values, prompt text, file contents, reasons, or paths.
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
    if result == "error":
        raise RuntimeError("telemetry sink unavailable")


def main():
    payload = load_payload()
    event = payload.get("hook_event_name") or ""
    tool_input = payload.get("tool_input") or {}

    if event == "PermissionDenied":
        _record("permission_denied",
                {"tool_name": payload.get("tool_name") or ""}, payload)
    elif event == "SubagentStart":
        _record("subagent_start", {"agent_type": payload.get("agent_type") or ""}, payload)
    elif event == "SubagentStop":
        _record("subagent_stop", {"agent_type": payload.get("agent_type") or ""}, payload)
    elif event == "PreToolUse":
        tool = payload.get("tool_name") or ""
        if tool == "Skill":
            skill = tool_input.get("skill") or tool_input.get("name") or tool_input.get("command") or ""
            _record("skill_load", {"skill": _norm_skill(skill)}, payload)
    elif event == "PostToolUse":
        file_path = tool_input.get("file_path") or ""
        if file_path and _TICKET_RE.search(file_path):
            _record("ticket_created", {"uid": _ticket_uid(file_path)}, payload)
        lang = _lang_bucket(file_path) if file_path else None
        if lang:
            _record("code_edit",
                    {"lang": lang, "ext": os.path.splitext(file_path)[1].lower()},
                    payload)
    elif event == "UserPromptSubmit":
        _record("turn", {"prompt_len": len(payload.get("prompt") or "")}, payload)
    elif event == "SessionStart":
        _record("session", {"phase": "start", "source": payload.get("source") or ""}, payload)
    elif event == "SessionEnd":
        _record("session", {"phase": "end", "end_reason": payload.get("reason") or ""}, payload)
    elif event == "PreCompact":
        _record("compaction", {}, payload)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--initialize":
        try:
            initialize_telemetry_db(sys.argv[2])
        except Exception:
            sys.exit(1)
        sys.exit(0)
    run(main)
