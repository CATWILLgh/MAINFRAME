---
id: aee3901b
title: adapters/codex/build_codex.py exceeds the 400-line guideline; split by concern
status: open
priority: low
component: codex-layer
discovered: 2026-07-14
discovered-from: []
tags: ["maintainability", "codex", "refactor"]
---

# aee3901b: adapters/codex/build_codex.py exceeds the 400-line guideline; split by concern

## What was observed
`adapters/codex/build_codex.py` is 702 lines after the Phase-2 gates addition (it was
already ~599 before, over the 400-line guideline; the gates work added ~110). It holds four
cohesive but separable concerns: skill rendering (`render_skill_dir`, `_rewrite_*`),
permission projection (`project_permissions`, `render_rules`), gate rendering
(`GATE_HOOKS`, `render_hooks_json`), and `main` orchestration.

## Why it is a problem
Soft maintainability guideline (hub CLAUDE.md: files under 400 lines). A single 700-line
generator is harder to navigate and review than four focused modules. The prose-rewrite
tables for `task-workflow` alone are ~140 lines and dominate the file.

## Why it is not a duplicate
- [#50f7fc38](50f7fc38-split-test-build-opencode.md) — splitting the OpenCode *test* file;
  this is the Codex *generator*.

## What probably needs to be done
- Extract into a small package: `_skills.py` (render + rewrites), `_permissions.py`
  (argv-prefix projection), `_gates.py` (`GATE_HOOKS` + hooks render), with `build_codex.py`
  as the thin `main` orchestrator. Keep the public names the tests import
  (`bc.render_skill_dir`, `bc.project_permissions`, `bc.render_hooks_json`, `bc.main`) as
  re-exports so `tools/test_build_codex.py` needs no churn.
- `tools/test_build_codex.py` is ~315 lines and growing — split alongside if it crosses 400.

## Acceptance criteria
- No single module over 400 lines; `test_build_codex.py` still green (15/15) with unchanged
  public import surface; `render_core --check` clean.

## Sources
- `adapters/codex/build_codex.py:1-702`
- hub `CLAUDE.md` — "Keep files under 400 lines and functions under 60 lines."

## Re-occurrence noted (2026-07-15)

The builder has grown to 797 lines. `_rewrite_task_workflow` spans `adapters/codex/build_codex.py:155-294` (140 lines), so both the file and a central transformation function now exceed the hub's own limits. The original modular split remains the right boundary, but the refactor also needs public-contract tests around each extracted transformation before code motion.
