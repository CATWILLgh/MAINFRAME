---
id: b39e1c99
title: Post-migration cleanup removes foreign symlinks solely by basename
status: approved
priority: medium
component: installer-safety
discovered: 2026-07-15
discovered-from: []
tags: ["installer", "migration", "symlink", "ownership", "destructive"]
---

# b39e1c99: Post-migration cleanup removes foreign symlinks solely by basename

## What was observed

`cleanup_stale_post_migration` has hard-coded lists of former MAINFRAME skill, agent, and hook names. For each matching path under `~/.claude`, it deletes any symlink without checking whether the link points into this repository, the former MAINFRAME layout, or an unrelated user-managed location. It also removes empty `agents` and `hooks` directories without evidence that the installer owns those directories.

## Why it is a problem

A user or another plugin can legitimately own a symlink with the same basename. Running the installer then removes external state outside the repository without proving ownership. The operation is silent beyond the generic “removed stale” message and is not safely reversible through the normal backup path.

## Why it is not a duplicate

The generic stale-link cleanup checks that resolved targets belong to the managed source directory. This migration-only cleanup omits that ownership check. Existing installer tickets cover missing sources, clobbered regular files, and non-transactional publication, not deletion of foreign symlinks by name.

## What probably needs to be done

- Remove only links whose resolved target matches a documented former MAINFRAME path or an installation manifest.
- Treat same-name foreign links as conflicts and leave them untouched.
- Route any actual removal through the safe backup mechanism.

## Acceptance criteria

- A same-name symlink to an unrelated target survives install and uninstall.
- A verified old MAINFRAME symlink is removed or backed up exactly once.
- Broken links are classified by owned target path, not basename alone.
- Isolated-home tests cover skills, agents, hooks, and the `rules` entry.
- Empty user-managed `agents` and `hooks` directories survive migration cleanup.
- A backup failure stops installation and is not reported as success.

## Sources

- `install.sh:906-975`
- `install.sh:845-875` — ownership-aware cleanup used elsewhere

## Resolution (2026-07-15)

**Implementer:** Codex primary agent
**Commit:** `3d6213aa334cb7def51a2a3b2867efa8858ecc6b`
**Summary:** Migration cleanup now recognizes ownership only from the exact raw absolute target produced by the former installer. Verified legacy links move through the reversible backup path; every foreign, broken, relative, or moved-checkout same-name link is preserved. Empty user layer directories are no longer removed.
**Claims to verify on audit:**
- Exact legacy links for skills, agents, hooks, and `hooks/rules` are backed up once.
- Foreign live and broken links survive install, repeat install, and uninstall.
- Relative and moved-checkout links are preserved as unverified ownership.
- Backup failure exits nonzero without reporting completion or deleting the original links.
- No real-home delivery was performed.

## Audit (2026-07-15)

**Auditor:** Independent read-only subagent (`stale_cleanup_final_review`)
**Verdict:** Approved
**Verified:**
- The ownership predicate compares raw link text with the historical absolute `${PROJECT_ROOT}/export/...` contract, including broken links.
- Mutation occurs outside conditional-function context, so `backup_target` failures propagate under `set -e`.
- The isolated suite covers foreign live and broken links, relative and moved-checkout links, all four legacy layers, idempotence, dry-run behavior, uninstall preservation, empty directories, and forced backup failure.
- All 31 Python test files passed. Shell syntax, render parity, diff whitespace, the base installer dry run, and the suppression-marker scan passed.
- Independent review found no actionable issue.
**Commit scope:** Only `install.sh` and `tools/test_install_migration_cleanup.py` were committed. User-owned `dist/claude-code/settings.json`, `.agents/`, and `.codex/` changes remained outside the commit.
