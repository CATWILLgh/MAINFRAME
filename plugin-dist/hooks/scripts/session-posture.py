#!/usr/bin/env python3
"""SessionStart hook: establish the hub working posture at session start and after compaction.

Opus 4.8 favors reasoning over tool calls and is less eager to load skills or
fan out sub-agents (recorded behavior). A steady CLAUDE.md line fades into the
background; a salient reminder at the moment context is fresh is more
action-triggering. This hook injects a tight posture POINTER — it does not load
skill bodies (there is no mechanism, and it would dilute attention); it tells the
agent when to load them and which posture to hold.

Single source of truth: the detailed procedure (the stop-vs-ticket rule, the
coverage gauge, the full cycle) lives in the `task-workflow` skill. This hook
only points at it and states the entry posture compactly, so it does not
duplicate CLAUDE.md or the skill body.

Fires on startup / resume / clear / compact (every fresh-context case).
Non-blocking (additionalContext only), fail-safe (any error -> exit 0), stdlib.
"""

import json
import sys

POSTURE = (
    "MAINFRAME working posture — engage the process, do not reason past it:\n"
    "- A task that MODIFIES code / config / docs / infra -> invoke the "
    "`task-workflow` skill BEFORE acting. Load it; do not run the process from "
    "memory.\n"
    "- Two phases. While the user is present: discuss + plan — widen coverage "
    "with recon sub-agents, and ask decision-level forks via `AskUserQuestion` "
    "(plain options + Other) until no decision-level unknown remains. Then "
    "execute to `/goal` or the agreed scope.\n"
    "- In execution: no questions — an out-of-scope finding -> `surface-ticket` "
    "and continue; STOP only for an un-discussed business-logic / functionality "
    "change that needs the user's decision.\n"
    "- Orchestrate by default: delegate broad / parallel / independent work "
    "(recon and execution) to sub-agents, in the background for fan-out; keep "
    "the main context for decisions and synthesis, not raw exploration."
)


def main():
    try:
        json.load(sys.stdin)  # consume the payload; posture is injected unconditionally
    except Exception:
        pass
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": POSTURE}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
