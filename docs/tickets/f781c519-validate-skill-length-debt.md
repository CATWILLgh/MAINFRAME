---
id: f781c519
title: validate-skill.py exceeds file and function length limits
status: open
priority: low
component: tools
discovered: 2026-07-15
discovered-from: []
tags: ["maintainability", "validator", "file-size", "function-size"]
---

# f781c519: validate-skill.py exceeds file and function length limits

## What was observed

`tools/validate-skill.py` is 445 lines, and `validate_skill()` spans lines 177-294 (118 lines). Both exceed the repository's own 400-line file and 60-line function limits.

## Why it is a problem

The main validation function mixes discovery, schema checks, token budgets, support-file validation, and result assembly. Changes to one rule require reviewing a large control flow in a tool that gates every shipped skill.

## Why it is not a duplicate

- [#98d286b1](98d286b1-detector-functions-over-60-lines.md) was limited to gate detectors and is resolved.
- [#aee3901b](aee3901b-build-codex-over-400-lines.md) covers the Codex builder.

## What probably needs to be done

- Extract cohesive validators with explicit result types while preserving the command-line and hook contracts.
- Characterize ordering, severity, and message text only where those are public behavior.

## Acceptance criteria

- Each module is under 400 lines and each function under 60 lines.
- `tools/test_validate_skill.py`, session-start output, and hook-mode behavior remain green.

## Sources

- `tools/validate-skill.py:1-445`, `tools/validate-skill.py:177-294`
