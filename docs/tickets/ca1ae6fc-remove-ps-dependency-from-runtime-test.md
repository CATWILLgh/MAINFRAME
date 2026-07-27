---
id: ca1ae6fc
title: Remove ps dependency from the Antigravity runtime unit test
status: open
priority: low
component: antigravity-hooks
discovered: 2026-07-27
discovered-from: ["#c2f6d19b"]
tags: ["testing", "sandbox", "processes", "antigravity"]
---

# ca1ae6fc: Remove ps dependency from the Antigravity runtime unit test

## What was observed

The full Python test sweep reaches six passing Antigravity runtime tests, then
`test_timeout_kills_detector_process_group` fails because it invokes `ps` to
inspect the child process state. The restricted local environment rejects
spawning `ps` with `PermissionError: operation not permitted`.

## Why it is a problem

The test is a Tier-1 regression check for bounded process-group cleanup, but its
assertion depends on a separately permissioned operating-system diagnostic.
That makes the complete local suite red even when the runtime behavior under
test is unchanged.

## Why it is not a duplicate

[#c2f6d19b](c2f6d19b-budget-and-isolate-antigravity-detectors.md) implemented
and audited the cleanup behavior. This ticket concerns a distinct portability
problem in the test's observation method, not the runtime implementation.

## What probably needs to be done

Replace the `ps` assertion with an in-process or filesystem-based child
liveness signal that remains observable after timeout without launching a
system process-inspection command. The replacement must still distinguish a
terminated child from a surviving or unreaped child.

## Acceptance criteria

- The test launches no `ps` or equivalent external process inspector.
- It still fails when a detector descendant survives timeout cleanup.
- `python3 tools/test_antigravity_runtime.py` passes in a process-restricted
  environment.

## Sources

- `tools/test_antigravity_runtime.py:146`
- [#c2f6d19b](c2f6d19b-budget-and-isolate-antigravity-detectors.md)
- Full local Python sweep on 2026-07-27:
  `PermissionError: operation not permitted: 'ps'`
