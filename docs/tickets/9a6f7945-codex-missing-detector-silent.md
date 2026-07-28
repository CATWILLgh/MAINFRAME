---
id: 9a6f7945
title: Codex hook launcher silently skips a missing mapped detector
status: open
priority: medium
component: codex-layer
discovered: 2026-07-15
discovered-from: []
tags: ["codex", "hooks", "degradation", "diagnostics", "fail-open"]
---

# 9a6f7945: Codex hook launcher silently skips a missing mapped detector

## What was observed

`mainframe-hook.sh` exits successfully as soon as the mapped detector file is absent. This happens before the launcher reads the payload and before the once-per-process degradation diagnostic used for a detector that exists but fails to run.

## Why it is a problem

A stale mapping, incomplete installation, or removed detector can silently disable a gate for the whole session. The deliberate fail-open policy prevents a frozen tool, but the user and model receive no signal that protection is missing.

## Why it is not a duplicate

- [#b86bf383](b86bf383-codex-gates-v1-followups.md) covers Codex runtime semantics and performance; it does not own missing-artifact diagnostics.
- [#6d09e7be](6d09e7be-install-sh-silent-success-on-missing-source.md) covers installer exit status and dangling links, not runtime launcher behavior.

## What probably needs to be done

- Route missing-detector and failed-detector cases through the same bounded, once-per-session degradation signal.
- Keep the host-facing exit successful so a broken optional installation cannot deny every tool call.
- Test both advisory and blocking mappings with a deliberately absent detector.

## Acceptance criteria

- A missing mapped detector produces one visible degradation message per session or parent process.
- Repeated calls do not flood output, and the tool call remains fail-open.
- Existing successful detector behavior and failure diagnostics remain unchanged.

## Sources

- `adapters/codex/gates/mainframe-hook.sh:15-20`, `adapters/codex/gates/mainframe-hook.sh:31-41`
- `core/gates/CONTRACT.md`
