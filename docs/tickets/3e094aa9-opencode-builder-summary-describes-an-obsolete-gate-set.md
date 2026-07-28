---
id: 3e094aa9
title: OpenCode builder summary describes an obsolete gate set
status: open
priority: low
component: opencode-diagnostics
discovered: 2026-07-15
discovered-from: []
tags: ["opencode", "diagnostics", "gates", "drift", "documentation"]
---

# 3e094aa9: OpenCode builder summary describes an obsolete gate set

## What was observed

`build_opencode.py` reports “two blocking security gates plus nine advisory hooks” and says Stop gates do not transfer. The current dispatcher reports 12 hook rows and implements five end-of-turn checks through `session.idle` prompting and notifications.

## Why it is a problem

The build summary is part of the adapter's verification output, but it understates current coverage and describes an obsolete limitation. Operators cannot reliably compare the expected adapter with the active plugin from this report.

## Why it is not a duplicate

[#74beb0fb](74beb0fb-opencode-stop-gate-emulation.md) implemented and closed the Stop-gate emulation. This ticket records the diagnostic text that was not updated with that change.

## What probably needs to be done

- Derive reported counts and capabilities from the same gate inventory used by the dispatcher or a shared generated manifest.
- Avoid prose counts that can drift independently.
- Test the summary against the active row and Stop-gate inventories.

## Acceptance criteria

- The builder summary matches the dispatcher inventory and current Stop-gate behavior.
- Adding or removing a gate changes the report without a second manual count edit.
- A test fails when diagnostic capability claims diverge from the plugin.

## Sources

- `adapters/opencode/build_opencode.py:290-299`
- `adapters/opencode/plugins/mainframe-gates.js:133-149`
- `adapters/opencode/plugins/mainframe-gates.js:354-395`
- [#74beb0fb](74beb0fb-opencode-stop-gate-emulation.md)
