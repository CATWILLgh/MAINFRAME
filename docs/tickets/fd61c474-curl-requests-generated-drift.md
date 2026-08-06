---
id: fd61c474
title: curl-requests generated surfaces drift from the core skill
status: closed
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

## Re-occurrence noted (2026-08-05)

**Noticed during:** ZCode writable-subagent lifecycle verification
**Where:** `python3 tools/render_core.py --check`
**Additional details:** The check still reports only
`dist/claude-code/plugin/skills/curl-requests/SKILL.md` as different from its
source. The ZCode adapter does not modify this generated skill.

## Resolution (2026-08-06)

**Implementer:** Claude Code (main session)
**Commits:** the `fix(rendering)` commit carrying
`dist/claude-code/plugin/skills/curl-requests/SKILL.md` and
`dist/codex/skills-golden/curl-requests/SKILL.md`, plus the `docs(tickets)`
commit carrying this file.
**Summary:** Both committed generated surfaces were regenerated from `core/`, so
the stale sentence claiming `~/.zshenv` sources the secret store into every
shell is gone from everything this repository publishes.
`dist/claude-code/plugin/skills/curl-requests/SKILL.md`
was refreshed with `python3 tools/render_core.py --write`;
`dist/codex/skills-golden/curl-requests/SKILL.md` was regenerated through
`build_codex.collect_skills` under the `HOME=/home/u` the golden test pins.
The Codex golden was a second, unreported red spot:
`test_real_repo_subset_matches_committed_goldens` was failing before this change.

Scope note for the auditor — the live installations behave differently per tool:

- **Claude Code was fixed immediately.** `~/.claude/skills/mainframe` is a
  symbolic link to `dist/claude-code/plugin`, so regenerating the render
  corrected the live skill in the same step.
- **Codex is still stale until the user reinstalls.** `dist/codex/{skills,bundle-v2}`
  and `dist/opencode/bundle-v2` carried the same stale text but are **untracked**;
  `install.sh` rebuilds them from source at install time
  (`install.sh:1026,1214`), so `~/.codex/skills/curl-requests/SKILL.md` keeps the
  false sentence until the next install run. Running that install was not part of
  this change.

On guarding: the committed surfaces were in fact covered — `dist/claude-code/`
by `render_core.py --check` and the Codex golden by its own unit test. Both were
red and neither was acted on, so the real weakness here was tolerance for a
failing check, not a missing one. The untracked bundles have nothing to drift
against in the repository; making an install refuse to publish a stale render is
already owned by
[#9ceb302c](9ceb302c-build-write-does-not-reconcile-state.md).

**Claims to verify on audit:**
- `python3 tools/render_core.py --check` reports no drift.
- `python3 tools/test_build_codex.py` is 31/31 (was 30/31, failing
  `test_real_repo_subset_matches_committed_goldens: Codex golden drift`).
- `tools/test_render_core.py` 39/39, `tools/test_build_opencode.py` 16/16,
  `tools/test_build_antigravity.py` 19/19.
- `grep -rn zshenv core/ dist/claude-code/ dist/codex/skills-golden/` returns nothing.
