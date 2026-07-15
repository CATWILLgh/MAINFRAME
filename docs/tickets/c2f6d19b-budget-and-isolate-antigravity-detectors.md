---
id: c2f6d19b
title: Budget Antigravity hook events and isolate detector failures
status: open
priority: high
component: antigravity-hooks
discovered: 2026-07-15
discovered-from: []
tags: ["antigravity", "hooks", "timeouts", "resilience", "security"]
---

# c2f6d19b: Budget Antigravity hook events and isolate detector failures

## What was observed

Every detector subprocess receives the same 10-second timeout, although shipped
detectors have internal contracts of 15, 30, 60, or 120 seconds. Events execute
up to four, seven, or five detectors sequentially. Generated hook handlers omit
their outer `timeout`, so Antigravity applies its documented 30-second default.

`Bridge.handle()` also catches failures around the whole event. A controlled
experiment returned `deny` from the first PreToolUse detector and raised from the
second; the final bridge result was `{}`, erasing the valid denial.

## Why it is a problem

Security, dependency, and architecture checks can be terminated precisely on
larger changes where they need more time. A slow or broken late detector can
also bypass an earlier destructive-command or secret-commit decision. Silent
fail-open is acceptable per detector, but not for the entire accumulated event.

## Why it is not a duplicate

- [#f4cf49f6](f4cf49f6-aggregate-antigravity-stop-detectors.md) covers multiple
  valid Stop blockers; this ticket covers timing and exceptional failures.
- [#d38d93a4](d38d93a4-add-antigravity-hook-diagnostics.md) covers visibility of
  failures, not preservation of decisions or execution budgets.

## What probably needs to be done

1. Define an explicit total budget for each hook event.
2. Reconcile that budget with every included detector's documented maximum.
3. Catch timeout, spawn, parse, and output errors per detector.
4. Preserve all valid decisions and notes produced before or after one failure.
5. Consider safe concurrency only where detectors have no ordering dependency.
6. Emit explicit handler `timeout` values in `hooks.json` that exceed the bridge
   budget by a small, named margin.

## Acceptance criteria

- A late exception cannot change an earlier `deny` or `ask` decision.
- Tests cover timeout, non-zero exit, malformed JSON, oversized output, missing
  executable, and success after a prior failure.
- Every event finishes within its configured Antigravity handler timeout.
- Long-running detector fixtures demonstrate that allowed detector contracts are
  not killed by the bridge's blanket timeout.
- Total latency and any concurrency assumptions are documented and measured.

## Sources

- `adapters/antigravity-2/gates/mainframe_hook.py:129-143`
- `adapters/antigravity-2/gates/mainframe_hook.py:167-180`
- `adapters/antigravity-2/gates/mainframe_hook.py:301-319`
- `adapters/antigravity-2/build_antigravity.py:104-112`
- <https://antigravity.google/docs/hooks>
