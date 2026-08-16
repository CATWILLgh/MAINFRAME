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

report_launcher_failure() {
    STATUS="$1"
    INPUT_PATH="${2:-}"
    FALLBACK_TMPDIR="${MAINFRAME_HOOK_FALLBACK_TMPDIR:-/tmp}"
    if [ -n "$INPUT_PATH" ]; then
        TMPDIR="$FALLBACK_TMPDIR" python3 "$DIR/hook-failure-report.py" \
            "$EVENT" "$0" "$STATUS" "$PPID" <"$INPUT_PATH" && return 0
    else
        # stdin is still the original hook payload when the first buffer fails.
        TMPDIR="$FALLBACK_TMPDIR" python3 "$DIR/hook-failure-report.py" \
            "$EVENT" "$0" "$STATUS" "$PPID" && return 0
    fi

    # No temporary storage is needed for this last-resort, bounded warning.
    printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"MAINFRAME hook failure: run-hook.sh could not create its private buffers during %s. The requested check is unavailable. Return this exact failure to your immediate caller before claiming the affected operation or task is verified. Do not retry or repair MAINFRAME unless assigned."},"systemMessage":"MAINFRAME hook failure: run-hook.sh could not create its private buffers during %s."}\n' \
        "$EVENT" "$EVENT" "$EVENT"
}

INPUT=$(mktemp "${TMPDIR:-/tmp}/mainframe-hook-input.XXXXXX") || {
    report_launcher_failure 73
    exit 0
}
OUTPUT=$(mktemp "${TMPDIR:-/tmp}/mainframe-hook-output.XXXXXX") || {
    report_launcher_failure 73 "$INPUT"
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
