---
id: a7c96692
title: Three independent gate detector→event mappings can drift; consider a shared core manifest
status: open
priority: low
component: gates
discovered: 2026-07-14
discovered-from: []
tags: ["gates", "hooks", "dry", "architecture", "cross-tool"]
---

# a7c96692: Three independent gate detector→event mappings can drift; consider a shared core manifest

## What was observed
The detector→hook-event mapping (which detector runs on PreToolUse vs PostToolUse vs Stop,
and for which tools) is now expressed THREE times, independently, one per tool adapter:

1. Claude Code — hand-authored `adapters/claude-code/gates/hooks.json`.
2. OpenCode — the `ROWS` + `STOP_GATES` tables in `adapters/opencode/plugins/mainframe-gates.js`.
3. Codex — the `GATE_HOOKS` dict in `adapters/codex/build_codex.py` (added 2026-07-14).

Each is maintained by hand. There is no single source that says "detector X is a blocking
PreToolUse gate on Bash-commit" — that fact is re-encoded in each adapter's dialect.

## Why it is a problem
Adding, renaming, or re-classifying a detector requires editing all three in lockstep.
A miss means a detector silently absent (or misclassified) on one tool while present on the
others — exactly the kind of silent-coverage-gap the launcher's fail-open design also risks.
The `core/gates/CONTRACT.md` already centralizes the *wire* contract; the *routing* is not
centralized. This is a DRY/single-source-of-truth violation (hub principle §4).

## Why it is not a duplicate
- [#cb173a75](cb173a75-shared-module-for-suppression-hooks.md) — shared *detector code*
  module (closed); this is about the shared *routing manifest*, not detector internals.

## What probably needs to be done
- Design a neutral `core/gates/manifest` (e.g. detector → {event, tools, mode:block|advisory})
  that all three adapters render from: CC `hooks.json`, OpenCode `ROWS`/`STOP_GATES`, Codex
  `GATE_HOOKS`. **requires verification** that each dialect's expressiveness maps cleanly
  (OpenCode's per-tool spawn filters, CC's matcher regex, Codex's `.*`).
- Until then: a cross-tool consistency test that flags a detector present in one adapter's
  mapping but missing from another (allowing intentional per-tool exclusions via an
  explicit allowlist).

## Acceptance criteria
- Either a single `core/gates` routing source renders all three adapter mappings, or a
  test fails when the three mappings diverge on a detector without an explicit exclusion note.

## Sources
- `adapters/claude-code/gates/hooks.json`
- `adapters/opencode/plugins/mainframe-gates.js` (`ROWS`, `STOP_GATES`)
- `adapters/codex/build_codex.py` (`GATE_HOOKS`)
- `core/gates/CONTRACT.md`
- `docs/principles.md` §4 (single source of truth)

## Re-occurrence noted (2026-07-15)

The repository-wide architecture audit confirmed that the drift risk is still unguarded. `tools/test_build_codex.py:277-282` verifies only that every Codex mapping names an existing detector; it does not compare event, mode, or tool coverage across Claude Code, OpenCode, and Codex. This leaves silent cross-adapter omission detectable only by manual review.

The acceptance criterion remains unchanged: a neutral manifest or an explicit semantic parity test must own the three mappings, with documented intentional exclusions.
