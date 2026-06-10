#!/usr/bin/env python3
"""SessionStart(compact) hook: one-line harness-feedback nudge after compaction.

A compaction event marks a long session — exactly where harness friction
(false-positive gate blocks, denied permissions, unclear rules) accumulates
and then dies unreported with the context. Inject a short reminder so still
-unreported friction gets filed via the `harness-feedback` skill. Also logs a
`feedback_nudge` telemetry row so nudge→report conversion is measurable.
Fail-safe: any error -> silent exit 0.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_note, load_payload, log_event, run
except Exception:
    sys.exit(0)

NUDGE = (
    "Post-compact check: this session has run long. If it hit mainframe-harness "
    "friction that is still unreported — a false-positive gate block, a wrongly "
    "denied permission, an unclear rule, a missing capability — file it via the "
    "`harness-feedback` skill once the current step completes. No friction — "
    "ignore this note."
)


def main():
    payload = load_payload()
    if payload.get("source") != "compact":
        return  # registered with matcher "compact"; re-check as boundary data
    log_event("feedback_nudge", {"trigger": "compact"}, payload)
    emit_note("SessionStart", NUDGE)


if __name__ == "__main__":
    run(main)
