---
id: fc226340
title: Secret commit gate scans a different repository or file set than git commit
status: open
priority: high
component: gates
discovered: 2026-07-15
discovered-from: []
tags: ["security", "secrets", "git", "commit", "command-parsing"]
---

# fc226340: Secret commit gate scans a different repository or file set than git commit

## What was observed

The gate derives the repository only from the hook payload working directory and reduces the commit command to a Boolean `-a` check. It then scans either the entire index or the entire `HEAD` diff. It does not model `git -C`, `--only`, `--include`, or pathspecs, all of which can change the repository or the exact set that Git commits.

## Why it is a problem

The gate can inspect a harmless set while Git commits a secret-bearing set, or block a commit because of a staged secret that the command explicitly excludes. A security gate must match the operation it authorizes.

## Why it is not a duplicate

- [#67388f9b](67388f9b-opencode-gate-binds-session-root-not-command-cwd.md) fixed OpenCode session-root binding and leading `cd`; it did not implement Git's repository and partial-commit command semantics.

## What probably needs to be done

- Parse the Git invocation into repository context and commit-selection semantics.
- Ask Git for the actual candidate patch where possible instead of reimplementing index rules.
- Fail conservatively, with a clear reason, when a supported commit form cannot be resolved.

## Acceptance criteria

- Tests prove correct scanning for the default index commit, `-a`, `git -C`, `--only`, `--include`, and pathspec commits.
- The test set includes both missed-secret and false-block cases.
- Existing simple `git commit` behavior remains unchanged.

## Sources

- `core/gates/detectors/secret-commit-gate.py:100-118`, `core/gates/detectors/secret-commit-gate.py:149-177`
- [Git commit documentation](https://git-scm.com/docs/git-commit.html)

## Deferred execution note (2026-07-15)

The candidate-index design completed dependency recon, installed-Git documentation verification, adversarial decision review, and an independent pre-implementation checkpoint. Execution was deliberately stopped before rendering because the required generated detector under `dist/claude-code/plugin/hooks/scripts/` is directly linked into the active local Claude environments. Updating it would violate the user's temporary delivery freeze. No source or rendered detector change was retained; the approved implementation plan remains at `~/.codex/plans/audit/MAINFRAME/2026-07-15-secret-commit-candidate-set.md`.
