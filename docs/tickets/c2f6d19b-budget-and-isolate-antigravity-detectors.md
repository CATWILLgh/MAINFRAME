---
id: c2f6d19b
title: Budget Antigravity hook events and isolate detector failures
status: approved
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

- `adapters/antigravity-2/gates/mainframe_hook.py:142-195`
- `adapters/antigravity-2/gates/mainframe_hook.py:295-329`
- `adapters/antigravity-2/gates/mainframe_runtime.py:19-89`
- `adapters/antigravity-2/gates/mainframe_runtime.py:111-237`
- `adapters/antigravity-2/build_antigravity.py:106-118`
- [Antigravity hooks](https://antigravity.google/docs/hooks)
- [Python `subprocess`](https://docs.python.org/3/library/subprocess.html)

## Resolution (2026-07-15)

**Implementer:** Codex
**Commit:** b857a31f9b9b620f420bc1ac9486958423178cbd
**Summary:** The adapter now owns one monotonic budget per event, starts each
independent detector concurrently, and applies results in declared order. Every
detector has a named allowance; the generated Antigravity handler timeout is
derived from the same contract with a five-second margin. Timeouts, process
spawn failures, non-zero exits, malformed or oversized output, and missing
scripts fail open only for the affected detector. On POSIX, each detector runs
in its own session and timeout cleanup kills and waits for its process group.

**Measured event shape:** Five controlled runs used every detector slot in each
event, with every fixture running for 0.25 seconds. Median bridge latency was
0.301 seconds for four `PreToolUse` detectors, 0.310 seconds for seven
`PostToolUse` detectors, and 0.309 seconds for five `Stop` detectors, versus
sequential baselines of 1.00, 1.75, and 1.25 seconds. A separate detector ran
successfully for 10.2 seconds under its 11-second allowance, proving removal of
the former blanket 10-second cutoff.

**Deferred bounds:** [#7b65ea21](7b65ea21-bound-detector-input-work.md) owns
unbounded detector input work; [#e0f591b1](e0f591b1-bound-memory-file-reads.md)
owns complete memory-file reads; [#f162d529](f162d529-terminate-windows-detector-trees.md)
owns Windows descendant cleanup. Live installed-plugin discovery remains under
[#bce23629](bce23629-live-antigravity-plugin-validation.md).

## Audit (2026-07-15)

**Auditor:** Independent Codex reviewer (`final_runtime_audit`)
**Verdict:** Approved
**Verified:**
- `ask` and `deny` survive a later timeout, and later advisory output remains
  deliverable after an earlier failure.
- Parallel process execution preserves declared result order and rejects late,
  unreaped, non-zero, malformed, missing, and oversized results independently.
- Output storage is bounded to 262,145 bytes and uses pipe backpressure rather
  than an unbounded temporary file.
- Cleanup has a two-second total wait budget; the Antigravity handler margin is
  larger and is emitted from the same runtime contract.
- A real POSIX detector grandchild is absent after timeout cleanup.
- The generated plugin includes the runtime module and explicit handler times.

**Regression scan:** The auditor independently passed runtime 6/6, hook 14/14,
builder 9/9, and `git diff --check`. The implementation run passed all 38 Python
test files, both Node suites, `Ruff`, the core render check, the `CLAUDE.md` and
skill validators, and native Antigravity 2.2.1 builder validation.
