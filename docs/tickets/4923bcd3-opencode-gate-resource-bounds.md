---
id: 4923bcd3
title: OpenCode gate timeouts do not terminate subprocesses and Git diff input is unbounded
status: open
priority: medium
component: opencode-plugin
discovered: 2026-07-15
discovered-from: []
tags: ["performance", "opencode", "hooks", "process-lifecycle", "resource-bounds"]
---

# 4923bcd3: OpenCode gate timeouts do not terminate subprocesses and Git diff input is unbounded

## What was observed

Advisory and Stop rows use `Promise.race()` to stop waiting after a timeout, but the spawned Python process is not cancelled or killed. The shared Git delta helper captures the complete zero-context `git diff HEAD` output in memory with no byte or file-count limit before parsing it.

## Why it is a problem

A timed-out detector can continue consuming CPU and memory after the caller has moved on. Large or adversarial working-tree diffs can amplify the cost across concurrently spawned gates and make timeout behavior look effective while work continues in the background.

## Why it is not a duplicate

- [#b86bf383](b86bf383-codex-gates-v1-followups.md) covers Codex matcher and launcher overhead, not OpenCode child-process ownership or shared diff bounds.

## What probably needs to be done

- Give `runProcess` a cancellation contract and terminate the full child process group on timeout, escalating only after a short grace period.
- Stream or bound Git diff parsing and define a conservative result when limits are exceeded.
- Measure representative large-change behavior before setting budgets.

## Acceptance criteria

- A timeout test proves the detector process and its descendants are no longer running.
- Diff parsing has explicit byte/file/time limits and a tested safe degradation result.
- Normal blocking rows still wait for a definitive decision and cannot turn a slow deny into a silent pass.

## Sources

- `adapters/opencode/plugins/mainframe-gates.js:227-287`
- `core/gates/detectors/_hooklib.py:207-236`
