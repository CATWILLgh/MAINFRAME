---
id: f4cf49f6
title: Aggregate every Antigravity Stop detector result before deciding
status: open
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
