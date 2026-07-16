#!/bin/sh
# Codex hook launcher for MAINFRAME hub gate detectors.
#
# Codex hands a hook the Claude-Code-compatible JSON payload on stdin (no args);
# this wrapper takes <event> <detector-basename> as args and lets the detector
# read the payload on stdin. Detectors live in Codex's own configuration tree,
# so a missing detector MUST
# degrade to a no-op, never a block: any nonzero exit here can be read by the
# host as a deny (a hub install absent for one session would otherwise freeze
# every tool call). All real blocking is JSON + exit 0 (core/gates/CONTRACT.md),
# so any nonzero exit below is an infrastructure failure, surfaced loudly (agent
# + user) once per parent process, then swallowed.

EVENT="$1"
NAME="$2"
DIR="${CODEX_HOME:-$HOME/.codex}/gates/detectors"
SCRIPT="${DIR}/${NAME}"

[ -f "$SCRIPT" ] || exit 0

# Detectors resolve the project boundary via CLAUDE_PROJECT_DIR, which Codex does
# not set (its payload carries `cwd`, not `project_dir`). Buffer the payload,
# derive the project dir from it structurally (json, so a crafted command string
# cannot spoof it the way a regex could), and export it — mirroring the OpenCode
# plugin, which sets CLAUDE_PROJECT_DIR from the payload before each detector.
PAYLOAD=$(cat)
CWD=$(printf '%s' "$PAYLOAD" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("cwd") or d.get("project_dir") or "")' 2>/dev/null)
[ -n "$CWD" ] && export CLAUDE_PROJECT_DIR="$CWD"

printf '%s' "$PAYLOAD" | python3 "$SCRIPT"
STATUS=$?
[ "$STATUS" -eq 0 ] && exit 0

LATCH="${TMPDIR:-/tmp}/mainframe-codex-hooks-degraded-$PPID"
[ -e "$LATCH" ] && exit 0

printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"mainframe harness DEGRADATION: hook script %s failed to launch (interpreter exit %s). Codex gates and reminders may be inactive for this whole session - do not assume they are running. Tell the user explicitly and suggest restarting Codex."},"systemMessage":"mainframe: hook %s failed to launch (exit %s) - harness degraded, gates/reminders may be off; consider restarting Codex."}\n' \
    "$EVENT" "$NAME" "$STATUS" "$NAME" "$STATUS"
mkdir "$LATCH" 2>/dev/null
exit 0
