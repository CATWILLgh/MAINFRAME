#!/bin/sh
# Hook launcher: convert interpreter-level launch failures into a LOUD no-op.
#
# python3 exits 2 when it cannot OPEN the script file (mid-session FS/EPERM
# outage, WeBuy 2026-06-20), and the hooks contract reads exit 2 on PreToolUse
# as BLOCK — so an unreadable hook froze every Bash call. In-script fail-safes
# cannot help: the failure precedes the script. No hub hook blocks via exit
# code (all blocking is JSON + exit 0), so ANY nonzero exit here is
# infrastructure failure by construction — safe to swallow, but never silently
# (user directive): notify the agent (additionalContext) and the user
# (systemMessage, honored on all hook events), once per parent process while a
# latch is possible, on every call when even the latch fails (total outage —
# loud is correct, a restart is needed anyway).
#
# Usage: run-hook.sh <HookEventName> <script.py>

EVENT="$1"
SCRIPT="$2"

python3 "$SCRIPT"
STATUS=$?
[ "$STATUS" -eq 0 ] && exit 0

LATCH="${TMPDIR:-/tmp}/mainframe-hooks-degraded-$PPID"
[ -e "$LATCH" ] && exit 0

NAME=$(basename "$SCRIPT" 2>/dev/null || printf 'hook')
printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"mainframe harness DEGRADATION: hook script %s failed to launch (interpreter exit %s). Plugin gates and reminders may be inactive for this whole session - do not assume they are running. Tell the user explicitly and suggest restarting Claude Code."},"systemMessage":"mainframe: hook %s failed to launch (exit %s) - harness degraded, gates/reminders may be off; consider restarting Claude Code."}\n' \
    "$EVENT" "$NAME" "$STATUS" "$NAME" "$STATUS"
mkdir "$LATCH" 2>/dev/null
exit 0
