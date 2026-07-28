---
id: 98d286b1
title: Six gate-detector functions exceed the 60-line rule (pre-existing, surfaced by the core/gates copy)
status: closed
priority: low
component: hooks
discovered: 2026-07-08
discovered-from: []
tags: ["code-quality", "hooks", "refactor"]
---

# 98d286b1: Six gate-detector functions exceed the 60-line rule (pre-existing, surfaced by the core/gates copy)

## What was observed

The `length-quality-note` Stop hook flags 6 functions over 60 lines in
`core/gates/detectors/` (byte-copies of the long-standing
`plugin-dist/hooks/scripts/` files, so the condition predates ADR 0085):

- `comment-discipline-reminder.py:105` `main` (64)
- `comment_extract.py:203` `_extract_generic` (153)
- `nodejs-security-scan.py:97` `main` (89)
- `nodejs-security-stop-gate.py:88` `main` (65)
- `python-security-scan.py:98` `main` (67)
- plus one more reported as "…and 1 more" (re-run the hook to enumerate).

## Why it is a problem

`export/CLAUDE.md` sets "functions under 60 lines"; the hub's own shipped
detectors violate the rule the hub enforces on every other project.
`_extract_generic` at 153 lines is the worst offender and the hardest to
review safely.

## Why it is not a duplicate

- [#e43819ea](e43819ea-length-gate-non-python-function-length.md) — covers the
  GATE's language-coverage gap; this ticket is about the flagged detector
  functions themselves.

## What probably needs to be done

Refactor each `main` into helper functions (parse payload / decide / emit) and
split `_extract_generic` by language family. Detectors are on the never-dark
list, so: one script per change, behavior pinned by the existing stdlib tests
(extend where a function has none) — NOT inside a neutral-core migration slice
(those must stay zero-behavior-change).

## Acceptance criteria

- `length-quality-note` reports zero function-length findings under
  `core/gates/detectors/`.
- Existing hook test suites stay green; changed detectors keep their
  block/note behavior on the current fixtures.

## Sources

- Stop-hook advisory output, 2026-07-08 session
- `export/CLAUDE.md` length rule; ADR 0085 (render/never-dark constraints)

## Resolution (2026-07-08)

**Implementer:** autonomous session
**Commits:** `e53d0b77caeb0c6fce8b1ca6b1c1a78ea50912ac`
**Summary:** The sixth function was enumerated via
`_length_check.over_threshold_functions` across `core/gates/detectors/`:
`python-security-stop-gate.py` `main` (61).

All six functions split into cohesive helpers — pure code motion, zero
behavior change, edited in `core/gates/detectors/` and rendered per ADR 0085:

- `comment-discipline-reminder.py` `main` 64 → 35 (`_targeted_note`,
  `_generic_note`)
- `comment_extract.py` `_extract_generic` 153 → 51 (`_consume_line_comment`,
  `_consume_block_comment`, `_skip_backtick`, `_skip_char_or_lifetime`,
  `_skip_string`, `_consume_construct`, `_skip_heredoc_body`)
- `nodejs-security-scan.py` `main` 89 → 33 (`_split_delta`,
  `_inherited_note`, `_delta_note`, `_MISSING_NOTE` constant)
- `nodejs-security-stop-gate.py` `main` 65 → 22 (`_classify`,
  `_delta_section`, `_inherited_section`)
- `python-security-scan.py` `main` 67 → 31 (`_split_delta`, `_delta_part`,
  `_inherited_part`, `_MISSING_NOTE` constant)
- `python-security-stop-gate.py` `main` 61 → 22 (`_classify`,
  `_delta_section`, `_inherited_section`)

Coverage added before the refactor (both uncovered targets pinned by
characterization tests, green against the unmodified code first):

- `tools/test_comment_extract.py` — 16 tests over `extract` /
  `extract_lenient` (Python exact path, JS/TS state machine, strings /
  templates / regex escapes must NOT extract, exotic-form file skip,
  heredoc, SQL, Rust nesting/lifetime, lenient documented FPs).
- `tools/test_comment_discipline_reminder.py` — 9 subprocess tests over
  `main` (targeted callout, docstring ephemeral reference, generic nudge,
  per-edit no-refire attribution, self-file / non-code / no-op silences).

**Claims to verify on audit:**
- `_length_check.over_threshold_functions` reports zero findings across
  `core/gates/detectors/`.
- All 27 `tools/test_*.py` suites pass, including
  `test_security_delta_scope` 28/28, `test_comment_extract` 16/16 and
  `test_comment_discipline_reminder` 9/9.
- `python3 tools/render_core.py --check` reports in sync.
