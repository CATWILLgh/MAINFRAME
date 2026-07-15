---
id: c72d5872
title: Split the oversized core renderer and its test module
status: open
priority: low
component: renderer
discovered: 2026-07-15
discovered-from: ["#40f67f95"]
tags: ["maintainability", "refactor", "testing"]
---

# c72d5872: Split the oversized core renderer and its test module

## What was observed

`tools/render_core.py` and `tools/test_render_core.py` were already 550 and 544 lines before the release work. The credential-resource ownership fix adds a small mapping to both, leaving them at 554 and 548 lines.

## Why it is a problem

Both files exceed the project's 400-line limit. Renderer planning, instruction composition, agent projection, permission merging, and their tests share one module, increasing the cost and risk of unrelated changes.

## Why it is not a duplicate

- [#3f750372](3f750372-reject-symlinked-render-targets.md) covers unsafe symbolic-link handling in the renderer, not module size and responsibility boundaries.

## What probably needs to be done

- Extract mapping/planning and adapter projection into focused modules with one owner per concern.
- Split tests along the same public boundaries without testing private implementation calls.
- Preserve `tools/render_core.py` as the stable command entry point.

## Acceptance criteria

- Each source and test module is under 400 lines.
- `python3 tools/test_render_core.py` and `python3 tools/render_core.py --check` remain green.
- The command-line interface and generated output remain byte-compatible.

## Sources

- `tools/render_core.py`
- `tools/test_render_core.py`
- Project `AGENTS.md` file-size rule

## Re-occurrence noted (2026-07-16)

**Noticed during:** integration of the Antigravity adapter into the installer TUI branch
**Where:** `tools/render_core.py` and `tools/test_render_core.py`
**Additional details:** The combined runtime-profile and portable-memory mappings remain semantically compatible and their tests pass, but the merged files are now 562 lines each. Splitting them is still outside the integration scope and remains required before the renderer satisfies the project limit.
