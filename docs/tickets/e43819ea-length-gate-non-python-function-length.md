---
id: e43819ea
title: length-quality-note only checks Python function length, not TS/JS/other languages
status: open
priority: low
component: hooks
discovered: 2026-07-06
discovered-from: []
tags: ["hooks", "code-quality", "scope-gap"]
---

# e43819ea: length-quality-note only checks Python function length, not TS/JS/other languages

## What was observed

`plugin-dist/hooks/scripts/length-quality-note.py` (Stop hook, advisory) enforces `export/CLAUDE.md`'s "functions under 60 lines" rule only for Python (`_length_check.python_function_spans`, via `ast.parse`). File-length (400 lines) is checked for any file in `_length_check.FILE_LENGTH_EXTENSIONS` (all `CODE_EXTENSIONS` minus `.sql`/`.vue`/`.svelte`), but function-length is Python-only.

## Why it is a problem

The rule in `export/CLAUDE.md:83` ("functions under 60 lines") is language-agnostic, but the hook only enforces half of its scope for non-Python projects (TypeScript/JavaScript, Go, Rust, etc.). A long function in a `.ts` file gets no advisory signal.

## Why it is not a duplicate

No existing ticket covers this; `length-quality-note.py` and `_length_check.py` were built 2026-07-06 (this session) with Python-only function detection as a deliberate v1 scope limit, not an oversight — see `~/.claude/plans/audit/MAINFRAME/2026-07-06-length-gate-hook.md`.

## What probably needs to be done

Per-language function-boundary detection carries real false-positive risk if done via regex heuristics (arrow functions, nested functions, JSX in TS/JS; no existing hub precedent for parsing non-Python function boundaries — confirmed via recon before building this hook). Options, requires verification of each before picking one:
- A proper parser/AST for TS/JS (e.g. an existing installed toolchain's AST, not a hand-rolled regex) if one is reliably available without adding a third-party Python dependency (hub hooks are stdlib-only).
- Check whether the existing `fallow` analyzer (already used by `fallow-quality-note.py` for TS/JS complexity/duplication) exposes a per-function line-count metric that could be reused instead of building a new parser — `fallow`'s `critical` findings already carry a `line_count` field per function (`fallow-quality-note.py:105`), verified NOT currently used for a standalone length check; may already contain everything needed for TS/JS function-length without new code.
- If neither is low-FP and stdlib/no-new-dependency, leave TS/JS function-length unenforced and only revisit if real friction data justifies the added complexity (hub's own "provable necessity" principle).

## Acceptance criteria

Decision recorded (build it, reuse `fallow`, or explicitly decline) with a source or experiment backing the choice — not a guess. If built: TDD tests mirroring `tools/test_length_check.py`'s Python coverage (nested scopes, decorators/arrow-function-equivalents, malformed-source fail-open).

## Sources

- `plugin-dist/hooks/scripts/_length_check.py` — current Python-only implementation.
- `plugin-dist/hooks/scripts/fallow-quality-note.py:100-106` — existing `line_count` field on critical-complexity findings.
- `export/CLAUDE.md:83` — the rule being enforced.
- `~/.claude/plans/audit/MAINFRAME/2026-07-06-length-gate-hook.md` — design history, decision-reviewer + advisor verdicts.
