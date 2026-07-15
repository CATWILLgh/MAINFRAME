---
id: e1ebe708
title: Apply Antigravity project gates to every active workspace root
status: open
priority: medium
component: antigravity-hooks
discovered: 2026-07-15
discovered-from: []
tags: ["antigravity", "multi-root", "hooks", "gates", "coverage"]
---

# e1ebe708: Apply Antigravity project gates to every active workspace root

## What was observed

Antigravity provides all active folders in `workspacePaths`, and the memory
identity deliberately combines them. In contrast, `_neutral_payload()` and
`_stop()` select only `roots[0]` as `project_dir` and `cwd`. Stop detectors scan
that first repository's Git diff and never inspect later workspace roots.

The current tests verify deterministic sorting of multiple paths but do not
assert that gates cover every root.

## Why it is a problem

Antigravity 2.0 explicitly supports projects containing multiple repositories.
Suppression markers, security findings, comment violations, and architecture
violations in a secondary root can pass unnoticed while the adapter reports a
successful stop decision.

## Why it is not a duplicate

- [#f4cf49f6](f4cf49f6-aggregate-antigravity-stop-detectors.md) combines detector
  results within one scan; this ticket expands the scan across project roots.
- Portable-memory multi-root identity is already intentional and is not the bug.

## What probably needs to be done

1. Define detector execution and aggregation across every canonical workspace.
2. Preserve tool-specific `Cwd` for commands while resolving file operations to
   the workspace containing their absolute target.
3. Aggregate per-root Stop reasons with unambiguous root labels.
4. Bound total work and integrate it with the event budget ticket.
5. Define behavior for missing, duplicate, nested, and non-Git roots.

## Acceptance criteria

- A two-repository test surfaces a violation present only in the second root.
- Reversing `workspacePaths` does not change the set of findings.
- Nested and duplicate roots are not scanned twice.
- A missing or non-Git root cannot suppress valid findings from another root.
- Multi-root execution remains within the configured event budget and produces a
  bounded deterministic reason.

## Sources

- `adapters/antigravity-2/gates/mainframe_hook.py:73-77`
- `adapters/antigravity-2/gates/mainframe_hook.py:145-161`
- `adapters/antigravity-2/gates/mainframe_hook.py:256-285`
- `tools/test_antigravity_hook.py:28-36`
- <https://antigravity.google/docs/features>
