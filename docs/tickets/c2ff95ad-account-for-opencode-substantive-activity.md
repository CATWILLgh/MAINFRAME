---
id: c2ff95ad
title: Define and count substantive OpenCode session activity
status: open
priority: medium
component: opencode-memory
discovered: 2026-07-15
discovered-from: []
tags: ["opencode", "memory", "events", "reminder", "business-logic"]
---

# c2ff95ad: Define and count substantive OpenCode session activity

## What was observed

`countTextUpdate()` ignores every message part except non-ignored `text`. The
test suite explicitly feeds a tool part containing more than 60 KiB and expects
no substantive activity. A session dominated by code reads, command output,
search results, or tool-driven discoveries can therefore remain below the
50 KiB reminder threshold even when it contains durable knowledge.

The implementation counts text growth carefully to avoid repeated streaming
updates, but there is no equivalent bounded rule for tool activity.

## Why it is a problem

The reminder is intended to approximate a substantive session, not assistant
prose volume. Tool-heavy engineering work is precisely where hard-won gotchas
and operational facts often emerge, so the proxy systematically misses an
important class of sessions.

## Why it is not a duplicate

- [#88c16c9d](88c16c9d-verify-opencode-reminder-dispatch-race.md) concerns safe
  dispatch after the reminder decision, not whether a reminder is warranted.
- [#05f18542](05f18542-make-opencode-memory-self-contained.md) concerns helper
  ownership and installation paths.

## What probably needs to be done

1. Define substantive activity in terms of observable OpenCode events.
2. Count bounded tool inputs/results or another stable session-size signal.
3. Deduplicate streaming replacements and repeated complete-part updates.
4. Cap any single tool contribution so one huge result cannot dominate forever.
5. Verify event shapes in both the installed CLI and desktop application.

## Acceptance criteria

- A tool-heavy fixture crossing the substantive threshold invokes the reminder
  detector even with little assistant text.
- Repeated updates to one tool part do not double-count identical bytes.
- One oversized result is capped by a named constant and cannot cause unbounded
  in-memory accounting.
- Trivial, ignored, and error-only sessions remain silent.
- Tests use real current event payload shapes from OpenCode CLI and Desktop.

## Sources

- `adapters/opencode/plugins/mainframe-memory.js:73-104`
- `adapters/opencode/plugins/mainframe-memory.js:144-159`
- `tools/test_mainframe_memory.mjs:261-270`
- `core/gates/detectors/memory-reminder.py:36-38`
- <https://opencode.ai/docs/plugins>
