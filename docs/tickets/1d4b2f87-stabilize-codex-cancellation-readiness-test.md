---
id: 1d4b2f87
title: Stabilize Codex cancellation readiness test under host contention
status: open
priority: medium
component: codexstate
discovered: 2026-07-22
discovered-from: []
tags: ["test", "timing", "codex", "process"]
---

# 1d4b2f87: Stabilize Codex cancellation readiness test under host contention

## What was observed

`TestAppServerClientKillsDescendantsOnInspectionCancellation` failed in both a
normal full Go run and a race-enabled full Go run when those suites ran in
parallel with release and adapter tests. The fake Codex script did not publish
`codex.ready` within the fixed two-second deadline. The same test then passed
10 consecutive normal runs and 3 consecutive race-enabled runs when isolated.

## Why it is a problem

The test is sensitive to machine contention rather than only the process-tree
contract it intends to verify. A false failure can make an otherwise valid
change appear regressed and can destabilize CI on a loaded runner.

## Why it is not a duplicate

No existing tracked ticket describes the fixed readiness deadline in this
Codex process-cancellation test. Runtime cancellation correctness and test
readiness synchronization are separate concerns.

## What probably needs to be done

- Replace the filesystem polling deadline with deterministic parent-child
  synchronization where practical.
- If a deadline remains necessary, separate process-start readiness from the
  cancellation latency assertion and derive a bounded host-tolerant limit.
- Preserve the descendant lifetime-pipe and process-group assertions.

## Acceptance criteria

- The test remains sensitive to a real failure to start or kill descendants.
- Repeated loaded runs do not fail solely because the ready file appears after
  two seconds.
- Normal and race-enabled `internal/codexstate` suites pass on macOS and Linux.

## Sources

- `internal/codexstate/app_server_process_unix_test.go:16`
- `internal/codexstate/app_server_process_unix_test.go:56`
- Verification on 2026-07-22: isolated `-count=10` normal and `-count=3 -race`
  both passed after two contention failures.
