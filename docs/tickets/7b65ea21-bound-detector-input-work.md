---
id: 7b65ea21
title: Bound detector input work before adapter deadlines
status: open
priority: medium
component: core-gates
discovered: 2026-07-15
discovered-from: ["c2f6d19b"]
tags: ["gates", "performance", "resource-bounds", "timeouts"]
---

# 7b65ea21: Bound detector input work before adapter deadlines

## What was observed

Several shared detectors perform work whose size depends directly on unbounded
input. Path validation expands every filesystem glob match. The comment Stop
gate reads and compares every changed code file, including a separate Git read
per file. Ticket scans have no explicit file-count ceiling. Memory loading has a
separate existing ticket for complete-file reads.

The Antigravity bridge now enforces finite per-detector deadlines. It stops the
detector itself on every target platform and owns the full descendant group on
POSIX. The detector contracts still do not define how much work is accepted or
how partial coverage is reported.

## Why it is a problem

A large glob, generated change set, or ticket tree can consume the whole gate
allowance and make the detector fail open. The bridge remains responsive, but
the project receives less safety coverage precisely on large changes.

## Why it is not a duplicate

- [#c2f6d19b](c2f6d19b-budget-and-isolate-antigravity-detectors.md) owns adapter
  scheduling, deadlines, and failure isolation, not detector input policy.
- [#e0f591b1](e0f591b1-bound-memory-file-reads.md) covers physical reads in the
  portable memory store only.

## What probably needs to be done

1. Define explicit file, match, byte, and elapsed-work limits at each detector
   input boundary.
2. Batch Git reads where possible instead of starting one command per file.
3. Return a distinct bounded-scan advisory when full coverage was not possible.
4. Preserve the current security decision for every item actually inspected.
5. Measure representative small, large, and generated repositories in every
   adapter that consumes the shared detectors.

## Acceptance criteria

- Glob expansion, changed-file comparison, and ticket scanning each have named
  deterministic bounds.
- Hitting a bound is visible and is not indistinguishable from a clean scan.
- Tests cover excessive matches, files, bytes, and slow filesystem operations.
- Typical repositories stay within the current Antigravity allowances.
- Claude Code, OpenCode, Codex, and Antigravity detector tests remain green.

## Sources

- `core/gates/detectors/path-validation.py:188-200`
- `core/gates/detectors/stop-gate-comment-discipline.py:36-58`
- `core/gates/detectors/_hooklib.py:256-278`
- `adapters/antigravity-2/gates/mainframe_runtime.py:49-85`
- [#e0f591b1](e0f591b1-bound-memory-file-reads.md)
