#!/usr/bin/env python3
"""Passive telemetry hook — silently records Bucket-1 behaviour facts.

Registered on several events (see the CC adapter source
`adapters/claude-code/gates/hooks.json`, rendered to
`plugin-dist/hooks/hooks.json`); branches on
`hook_event_name`, writes one metadata row via `_hooklib.log_event`, and emits
NOTHING to stdout, so it is invisible to the agent. Best-effort and fail-safe:
any error is swallowed by `run()` / `log_event`. Privacy: only low-risk metadata
is extracted — never `tool_input` values, prompt text, file contents, or paths.
See `docs/layers/hooks.md` §1.7 and ADR 0073.
"""

import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import load_payload, log_event, run
except Exception:
    sys.exit(0)

_TICKET_RE = re.compile(r"[/\\]docs[/\\]tickets[/\\].+\.md$")
_COMPONENT_RE = re.compile(r"^component:\s*(.+)$", re.MULTILINE)

# Coarse domain buckets for code edits — only languages a profile sub-agent owns are
# kept; everything else returns None and is not logged, so `code_edit` stays a clean
# denominator for measuring profile-agent under-use (ADR 0073).
_EXT_LANG = {
    ".tsx": "frontend", ".jsx": "frontend",
    ".css": "frontend", ".scss": "frontend", ".sass": "frontend", ".less": "frontend",
    ".vue": "frontend", ".svelte": "frontend",
    ".ts": "ts",
    ".py": "python",
}


def _ticket_component(file_path):
    # Extract only the `component:` tag from a freshly-written ticket — never log
    # the path or body.
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(2000)
        match = _COMPONENT_RE.search(head)
        return match.group(1).strip() if match else ""
    except Exception:
        return ""


def _ticket_uid(file_path):
    # Hash of the ticket's basename — lets DISTINCT tickets be counted without logging
    # the descriptive slug or the path (privacy). Rewrites of the same file share the
    # uid, so create-vs-rewrite is separable in analysis.
    base = os.path.basename(file_path)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]


def _norm_skill(raw):
    # Strip the plugin namespace (`mainframe:task-workflow` -> `task-workflow`) so the
    # same skill aggregates into one bucket regardless of how it was invoked.
    name = str(raw).split()[0] if raw else ""
    return name.split(":")[-1]


def _lang_bucket(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    return _EXT_LANG.get(ext)


def main():
    payload = load_payload()
    event = payload.get("hook_event_name") or ""
    tool_input = payload.get("tool_input") or {}

    if event == "PermissionDenied":
        log_event("permission_denied",
                  {"tool_name": payload.get("tool_name") or "",
                   "reason": payload.get("reason") or ""}, payload)
    elif event == "SubagentStart":
        log_event("subagent_start", {"agent_type": payload.get("agent_type") or ""}, payload)
    elif event == "SubagentStop":
        log_event("subagent_stop", {"agent_type": payload.get("agent_type") or ""}, payload)
    elif event == "PreToolUse":
        tool = payload.get("tool_name") or ""
        # advisor is a server-side `server_tool_use` (resolved inside the /v1/messages
        # call), never executed client-side — so it never reaches the tool-use hooks; only Skill does.
        if tool == "Skill":
            skill = tool_input.get("skill") or tool_input.get("name") or tool_input.get("command") or ""
            log_event("skill_load", {"skill": _norm_skill(skill)}, payload)
        elif tool == "TodoWrite":
            # Counts only — never the todo text, which can carry task descriptions.
            todos = tool_input.get("todos") or []
            counts = {"pending": 0, "in_progress": 0, "completed": 0}
            for item in todos:
                status = (item or {}).get("status")
                if status in counts:
                    counts[status] += 1
            log_event("todo_write", {"n": len(todos), **counts}, payload)
    elif event == "PostToolUse":
        file_path = tool_input.get("file_path") or ""
        if file_path and _TICKET_RE.search(file_path):
            log_event("ticket_created",
                      {"component": _ticket_component(file_path),
                       "uid": _ticket_uid(file_path)}, payload)
        lang = _lang_bucket(file_path) if file_path else None
        if lang:
            log_event("code_edit",
                      {"lang": lang, "ext": os.path.splitext(file_path)[1].lower()},
                      payload)
    elif event == "UserPromptSubmit":
        log_event("turn", {"prompt_len": len(payload.get("prompt") or "")}, payload)
    elif event == "SessionStart":
        log_event("session", {"phase": "start", "source": payload.get("source") or ""}, payload)
    elif event == "SessionEnd":
        log_event("session", {"phase": "end", "reason": payload.get("reason") or ""}, payload)
    elif event == "PreCompact":
        log_event("compaction", {}, payload)


if __name__ == "__main__":
    run(main)
