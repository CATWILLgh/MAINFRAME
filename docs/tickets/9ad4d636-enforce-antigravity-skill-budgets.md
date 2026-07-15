---
id: 9ad4d636
title: Make projected Antigravity skills pass every size budget
status: open
priority: medium
component: antigravity-projection
discovered: 2026-07-15
discovered-from: []
tags: ["antigravity", "skills", "projection", "validation", "prompt-budget"]
---

# 9ad4d636: Make projected Antigravity skills pass every size budget

## What was observed

The Antigravity builder successfully generated 147 files, but validating every
generated skill reported two warnings:

- projected `react-frontend-patterns/forms.md` contains 61 non-empty lines,
  above the 60-line supporting-file limit;
- projected `task-workflow/SKILL.md` contains 5,026 body tokens, above the
  5,000-token post-compaction limit.

The corresponding source skills pass direct validation. The warnings appear
only after `_adapt_markdown()` expands runtime-specific paths and phrases during
Antigravity projection. The current CI loop invokes `validate-skill.py`, whose
documented exit contract allows warnings, so the generated package remains green.

## Why it is a problem

These limits protect prompt completeness after compaction and keep supporting
material small enough to load predictably. Shipping a generated package beyond
them creates adapter-specific prompt drift that source-skill validation cannot
see. This is medium priority: it violates the hub's validation standard and adds
technical debt, but the builder, native manifest validation, and runtime tests
still pass.

## Why it is not a duplicate

- [#3efdbdb9](3efdbdb9-correct-antigravity-runtime-skill-guarantees.md) covers
  unsupported Claude-specific behavioral claims in projected skills. This ticket
  covers measurable size regressions introduced by the projection transform.
- [#bce23629](bce23629-live-antigravity-plugin-validation.md) covers activation
  in a real desktop session. This ticket is deterministic and can be closed in
  the repository without access to the desktop runtime.

## What probably needs to be done

1. Measure every projected skill after `_adapt_markdown()` rather than relying
   only on validation of the neutral source tree.
2. Restore headroom by tightening the neutral source, using shorter Antigravity
   rewrites, or applying a narrowly owned adapter overlay where semantics differ.
3. Add a generator regression that treats size-budget warnings in the generated
   Antigravity skill tree as failures while preserving the validator's general
   warning contract for interactive use.
4. Keep the projection allowlist or overlay decision aligned with #3efdbdb9 so
   the two fixes do not introduce competing ownership.

## Acceptance criteria

- Every generated Antigravity skill reports zero `BODY-TOKENS`, `BODY-LINES`,
  `SUPP-TOKENS`, and `SUPP-LINES` findings.
- `react-frontend-patterns/forms.md` has at most 60 non-empty projected lines.
- `task-workflow/SKILL.md` has at most 5,000 projected body tokens with explicit
  safety headroom for future runtime-path rewrites.
- `tools/test_build_antigravity.py` fails if a future projection crosses any of
  those budgets.
- The full skill validator, Antigravity builder tests, and native plugin manifest
  validation pass.

## Sources

- `adapters/antigravity-2/build_antigravity.py:31-78` — runtime rewrites that
  expand projected skill text.
- `adapters/antigravity-2/build_antigravity.py:230-241` — skill collection and
  projection.
- `tools/validate-skill.py:61-66` — hub size limits.
- `tools/validate-skill.py:232-287` — body and supporting-file measurements.
- Verification command on 2026-07-15: build to an isolated directory, then run
  `tools/validate-skill.py` for every generated `skills/*` directory.
