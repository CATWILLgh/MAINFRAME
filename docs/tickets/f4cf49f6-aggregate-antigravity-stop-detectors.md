---
id: f4cf49f6
title: Aggregate every Antigravity Stop detector result before deciding
status: approved
priority: high
component: antigravity-hooks
discovered: 2026-07-15
discovered-from: []
tags: ["antigravity", "hooks", "business-logic", "gates"]
---

# f4cf49f6: Aggregate every Antigravity Stop detector result before deciding

## What was observed

`Bridge._stop()` returns as soon as the first detector reports
`decision == "block"`. A controlled runner that returned a block for every member of
`STOP_DETECTORS` invoked only `stop-gate-suppression-markers.py`; the other four
detectors were never evaluated. The loop stamp is also checked inside this
early-return branch instead of after aggregation.

If Antigravity reuses `executionNum`, the retry consumes the stamp and permits
termination without evaluating later gates. If it increments `executionNum`,
the same first detector can block again while later gates remain starved.

## Why it is a problem

The adapter collapses five independently owned Stop hooks into one command but
does not preserve their combined semantics. A user can fix the first surfaced
violation and still receive an incomplete result, or the execution loop can
repeat without ever reporting the remaining blockers.

## Why it is not a duplicate

- [#bce23629](bce23629-live-antigravity-plugin-validation.md) verifies live hook
  discovery and ordering; it does not define aggregation inside the bridge.
- [#c2f6d19b](c2f6d19b-budget-and-isolate-antigravity-detectors.md) covers
  time budgets and detector failures, not valid multiple-block results.

## What probably needs to be done

1. Run every applicable Stop detector and collect all valid block reasons.
2. Produce one deterministic, bounded reason that identifies every blocker.
3. Apply one conversation/execution loop guard after aggregation.
4. Define and test behavior for both reused and incremented `executionNum`.
5. Preserve fail-open behavior for invalid detector output without suppressing
   valid results from other detectors.

## Acceptance criteria

- A test with at least three blocking detectors proves all three are invoked and
  represented in the returned reason.
- Detector order does not change which blockers are retained.
- A repeated Stop cannot loop indefinitely and cannot silently skip detectors
  that were not evaluated on the previous pass.
- Memory reminders run only after the blocking-gate decision is complete.
- Existing single-block and no-block hook tests remain green.

## Sources

- `adapters/antigravity-2/gates/mainframe_hook.py:256-285`
- `tools/test_antigravity_hook.py:181-204`
- <https://antigravity.google/docs/hooks>

## Resolution (2026-07-15)

**Implementer:** Codex
**Commits:** 14a67cae5758025a50402518d633bbc73b3e27a3
**Summary:** The bridge now evaluates every Stop detector before deciding,
combines all blockers into one deterministic response, reserves an untruncated
detector manifest, and bounds UTF-8 details to 30,000 bytes. The loop stamp is
applied once after aggregation, so repeated stops re-run every gate without
continuing indefinitely.
**Claims to verify on audit:**
- Every name in `STOP_DETECTORS` is invoked once before a blocking decision.
- Empty, non-string, invalid, reordered, and oversized detector outputs retain
  every valid blocker without exceeding `MAX_STOP_REASON_BYTES`.
- The same `executionNum` rechecks all gates but continues only once; a new
  `executionNum` can continue again.
- `memory-reminder.py` does not run while any Stop gate blocks.
- `tools/test_antigravity_hook.py` passes 13 tests and all repository Python/Node
  suites, render checks, and validators remain green.

## Audit (2026-07-15)

**Auditor:** Independent Codex reviewer (`stop_ticket_audit`)
**Verdict:** Approved
**Verified:**
- Commit `14a67ca` invokes all five Stop detectors before deciding and preserves
  every valid blocker in a deterministic, bounded UTF-8 response.
- Same-execution and incremented-execution loop behavior matches the resolution
  claims, and the memory reminder is excluded while blockers exist.
- Empty, non-string, invalid, reordered, and oversized outputs are covered without
  weakened assertions or suppression markers.
**Regression scan:** 41/41 affected checks passed independently: hook 13/13,
builder 9/9, lifecycle 2/2, installer 17/17, plus a current generated-plugin check.
The implementer's broader 37-file Python run, both Node suites, render checks, and
validators were reviewed as session evidence rather than rerun by the auditor.
**Notes:** No scope creep into detector exception isolation or timeout budgeting.
