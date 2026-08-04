---
id: fd61c474
title: curl-requests generated surfaces drift from the core skill
status: open
priority: medium
component: rendering
discovered: 2026-08-04
discovered-from: []
tags: ["skills", "rendering", "golden", "tests"]
---

# fd61c474: curl-requests generated surfaces drift from the core skill

## What was observed

The pre-change adapter baseline fails two tests because `core/skills/curl-requests/SKILL.md` differs from both `dist/claude-code/plugin/skills/curl-requests/SKILL.md` and the committed Codex golden for the same skill. The focused baseline completed with 96 passing tests and these two failures:

- `tools/test_render_core.py::test_real_repo_is_drift_free`
- `tools/test_build_codex.py::test_real_repo_subset_matches_committed_goldens`

The working tree contained no modification to the core skill or either generated copy when the failure was reproduced.

## Why it is a problem

Generated drift makes the repository's ordinary renderer and Codex projection gates red before unrelated adapter work starts. It can also mask a new regression because a full focused run cannot return green until the pre-existing mismatch is resolved.

## Why it is not a duplicate

No ticket mentioning the `curl-requests` generated or golden drift was found. Existing `curl-requests` references concern activation telemetry and credential migration rather than render consistency.

## What probably needs to be done

- Determine whether the core source change is the intended contract.
- Regenerate the Claude Code projection through `tools/render_core.py`.
- Regenerate the Codex committed golden through the owning adapter workflow.
- Review the resulting semantic diff before committing generated artifacts.

## Acceptance criteria

- `python3 -m pytest -q tools/test_render_core.py tools/test_build_codex.py tools/test_build_opencode.py tools/test_build_antigravity.py` passes.
- `python3 tools/render_core.py --check` reports no drift.
- The core source, Claude Code render, and Codex golden retain the intended `curl-requests` contract.

## Sources

- `core/skills/curl-requests/SKILL.md`
- `dist/claude-code/plugin/skills/curl-requests/SKILL.md`
- `dist/codex/skills-golden/curl-requests/SKILL.md`
- Baseline test run on 2026-08-04: 96 passed, 2 failed.
