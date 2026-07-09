#!/usr/bin/env python3
"""Multi-event hook: keep `task-workflow` actively engaged, not merely present.

A skill survives compaction — Claude Code re-attaches the first 5K tokens of each
previously-invoked skill after the summary (`code.claude.com/docs/en/skills`), and
the runtime frames the re-attached copy "for context only, do not re-execute". Per
Anthropic's own docs, such content is often deprioritised: "the content is usually
still present and the model is choosing other tools or approaches." So the process
skill can sit in context yet stop driving the work — most visibly after a
compaction. The hub keeps it <=5K precisely so it survives, but surviving is not the
same as being followed.

This hook re-activates it at the point of action. Per session segment (reset on
every SessionStart, including compact) it tracks whether `task-workflow` was actively
invoked. On the first file-modifying tool call (Edit/Write/MultiEdit) by the MAIN
agent in a segment where it was not, it emits a non-blocking note to invoke it now —
a re-attached copy is deprioritised background, so re-invoking re-activates the
cycle. Fires once per segment.

Events: SessionStart (reset), PreToolUse:Skill (mark active), PreToolUse on
Edit/Write/MultiEdit (check + remind). Main agent only — subagents cannot invoke
skills. Advisory (additionalContext only), fail-safe (any error -> exit 0), stdlib.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import _hooklib
    from _hooklib import (load_payload, emit_note, run, tw_engagement_path,
                          tw_engagement_state)
except Exception:
    sys.exit(0)

SKILL_NAME = "task-workflow"
MODIFY_TOOLS = ("Edit", "Write", "MultiEdit")

NOTE = (
    "Before modifying files: invoke the `task-workflow` skill now if you have not "
    "this session segment. It defines the cycle you are about to run (recon -> "
    "advisor -> TDD -> verify -> ticket -> commit). A copy re-attached after a "
    "compaction is deprioritised background, and its 'shown for context only, do "
    "not re-execute' framing means do not re-run one-time setup — it does NOT mean "
    "skip the process. Re-invoke to re-activate, then proceed. (A trivial, "
    "reversible, single-file mechanical edit may proceed without it — but 'too "
    "small for the process' is the usual tell that you are dropping a step you "
    "should not.)"
)


def _write_state(path, value):
    try:
        os.makedirs(_hooklib.TW_ENGAGE_STATE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(value)
    except Exception:
        pass


def _norm_skill(raw):
    name = str(raw).split()[0] if raw else ""
    return name.split(":")[-1]


def _in_project(file_path, cwd):
    """True unless the target provably resolves outside the project cwd. The
    cycle governs project modifications only — and a false nudge on
    housekeeping (auto-memory, /tmp) would also burn the once-per-segment
    reminder before the first real project edit. Missing path or cwd keeps
    today's behavior (fail-open)."""
    if not file_path or not cwd:
        return True
    try:
        root = os.path.realpath(os.path.expanduser(cwd))
        target = os.path.realpath(
            os.path.join(root, os.path.expanduser(file_path)))
    except (OSError, ValueError):
        return True
    return target == root or target.startswith(root + os.sep)


def main():
    payload = load_payload()
    event = payload.get("hook_event_name") or ""
    session_id = str(payload.get("session_id") or "")
    path = tw_engagement_path(session_id)

    if event == "SessionStart":
        _write_state(path, "fresh")
        return

    # Subagents cannot invoke skills (narrow tools, no Skill); only the main agent
    # (empty agent_id) is gated, so the nudge never reaches a context that can't act.
    if payload.get("agent_id"):
        return

    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    if tool == "Skill":
        skill = (tool_input.get("skill") or tool_input.get("name")
                 or tool_input.get("command") or "")
        if _norm_skill(skill) == SKILL_NAME:
            _write_state(path, "active")
        return

    if tool in MODIFY_TOOLS:
        if not _in_project(tool_input.get("file_path") or "",
                           payload.get("cwd") or ""):
            return
        if tw_engagement_state(session_id) in ("active", "reminded"):
            return
        emit_note("PreToolUse", NOTE)
        _write_state(path, "reminded")


if __name__ == "__main__":
    run(main)
