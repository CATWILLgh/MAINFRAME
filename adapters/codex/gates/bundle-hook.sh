#!/bin/sh

EVENT="$1"
NAME="$2"
BUNDLE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) || exit 0
SCRIPT="${BUNDLE_DIR}/gates/detectors/${NAME}"

[ -f "$SCRIPT" ] || exit 0

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
