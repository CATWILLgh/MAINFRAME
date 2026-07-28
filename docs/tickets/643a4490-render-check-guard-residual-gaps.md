---
id: 643a4490
title: render_core --check residual gaps — file-wide lint allow-tokens and unmanaged plugin-dist/hooks root
status: closed
priority: low
component: tools
discovered: 2026-07-08
discovered-from: []
tags: ["neutral-core", "render", "guard-gap"]
---

# 643a4490: render_core --check residual gaps — file-wide lint allow-tokens and unmanaged plugin-dist/hooks root

## What was observed

Reviewer #2 of the wave-1 gates slice (approve, Low findings):

1. The naked-render-path lint matches allow tokens (`core/gates`, `render`)
   file-wide, not per line (`tools/render_core.py`, `lint()`). A core detector
   containing "render" anywhere passes even if another line holds a naked
   `plugin-dist/` reference. Deliberate tradeoff (line-level matching
   false-positives on prose wrapped across physical lines — real corpus case:
   the `hooklib-smoke-check.py` note); documented in the module docstring.
2. Orphan detection covers only directory-sourced targets (`scripts/`,
   `rules/`). A stray file dropped at the `plugin-dist/hooks/` root (next to
   `hooks.json`) is neither rendered nor flagged. Currently nothing unmanaged
   lives there.

## Why it is a problem

Both are false-negative holes in a secondary guard. Low impact today; they
matter more as the managed surface grows in later waves (agents, skills).

## Why it is not a duplicate

First ticket about `render_core.py` guard granularity; unrelated to
[#98d286b1](98d286b1-detector-functions-over-60-lines.md) (detector function
length) and [#3cd20dc8](3cd20dc8-hub-semgrep-rules-dir-never-found.md)
(semgrep rules path bug).

## What probably needs to be done

1. Lint: match per paragraph or per line-window instead of file-wide, keeping
   the wrapped-prose case green (the existing corpus-shaped tests pin it).
2. Orphans: add explicit managed-root support to the manifest (e.g. a
   `managed_dirs` list independent of mappings) so `plugin-dist/hooks/` root is
   swept; revisit when the agents/skills waves extend the manifest anyway.

## Acceptance criteria

- A file mixing one naked and one render-aware `plugin-dist/` reference is
  flagged; the wrapped-prose fixtures stay green.
- A stray file at `plugin-dist/hooks/` root fails `--check` as an orphan.

## Sources

- `tools/render_core.py` (`lint()`, `check()`), `tools/test_render_core.py`
- Reviewer #2 verdict, 2026-07-08 (wave-1 gates slice)

## Resolution (2026-07-08)

**Implementer:** autonomous session (Fable 5)
**Commits:** `997004ebb48e7855af204392eb28e342888e03df`
**Summary:** lint now matches allow tokens in a ±2-line window per reference
(`LINT_WINDOW`), so a naked reference is flagged even when the file has a
render-aware one elsewhere; orphan detection extends to parents of
file-mapped targets (immediate files), covering the `plugin-dist/hooks` root.
**Claims to verify on audit:**
- `tools/test_render_core.py` — 24/24, incl.
  `test_lint_flags_naked_line_even_with_aware_reference_elsewhere` and
  `test_stray_file_at_file_mapping_root_is_orphan`.
- Wrapped-prose fixtures (`test_lint_allows_render_aware_phrasing`) still green.
- `python3 tools/render_core.py --check` — in sync on the real repo.
