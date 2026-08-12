#!/bin/sh
# Keep telemetry registrations inert outside this adapter's --dev installation.
# This gate intentionally runs before run-hook.sh creates temp files or starts
# Python. MAINFRAME_TELEMETRY_DB is an explicit test/debug override.

if [ -z "${MAINFRAME_TELEMETRY_DB:-}" ]; then
    [ -n "${HOME:-}" ] || exit 0
    [ -d "$HOME/.claude/mainframe/claude-code/telemetry" ] || exit 0
fi

DIR=$(dirname "$0")
exec sh "$DIR/run-hook.sh" "$@"
