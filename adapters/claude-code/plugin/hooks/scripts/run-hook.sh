#!/bin/sh
# Run one hook without turning an infrastructure failure into a tool denial.
#
# The hook payload is buffered so the failure reporter sees the same session
# identity as the failed script. Successful stdout is passed through exactly;
# failed/partial stdout is discarded and replaced by one role-neutral report.

EVENT="$1"
SCRIPT="$2"
DIR=$(dirname "$0")
umask 077
INPUT=$(mktemp "${TMPDIR:-/tmp}/mainframe-hook-input.XXXXXX") || exit 0
OUTPUT=$(mktemp "${TMPDIR:-/tmp}/mainframe-hook-output.XXXXXX") || {
    rm -f "$INPUT"
    exit 0
}
trap 'rm -f "$INPUT" "$OUTPUT"' EXIT HUP INT TERM

cat >"$INPUT"
python3 "$SCRIPT" <"$INPUT" >"$OUTPUT"
STATUS=$?
if [ "$STATUS" -eq 0 ]; then
    cat "$OUTPUT"
    exit 0
fi

python3 "$DIR/hook-failure-report.py" \
    "$EVENT" "$SCRIPT" "$STATUS" "$PPID" <"$INPUT" && exit 0

# The reporter is itself part of the failed infrastructure. Stay role-neutral
# and loud; duplicate output is preferable to an invisible safety-net outage.
NAME=$(basename "$SCRIPT" 2>/dev/null || printf 'hook')
printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"MAINFRAME hook failure: %s did not complete during %s (exit %s), and its failure reporter also failed. Return this exact failure to your immediate caller before claiming the affected operation or task is verified. Do not retry or repair MAINFRAME unless assigned."},"systemMessage":"MAINFRAME hook failure: %s failed during %s (exit %s); failure reporter unavailable."}\n' \
    "$EVENT" "$NAME" "$EVENT" "$STATUS" "$NAME" "$EVENT" "$STATUS"
exit 0
