---
id: 20e75df1
title: Model creation and rollback of managed target directories
status: open
priority: medium
component: installer
discovered: 2026-07-16
discovered-from: ["#7a1c1d1d"]
tags: ["tui", "directories", "recovery", "ownership"]
---

# 20e75df1: Model creation and rollback of managed target directories

## What was observed

The recoverable link workspace can safely mutate a link only after its parent
directory exists. A first installation may target missing roots such as
`~/.local/bin`, `~/.codex`, or an adapter configuration directory. Creating
those directories implicitly inside a link operation would not record their
ownership or make their rollback observable.

## Why it is a problem

Without an explicit directory lifecycle, a failed or reverted installation can
leave new directory trees behind, apply unintended modes, or remove a directory
that another process populated after it was created. The current link journal
records link before/after images, not directory creation and emptiness.

## Why it is not a duplicate

- [#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) covers recoverable
  execution of a valid plan; this ticket defines missing directory operations
  that such a plan must contain.
- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) covers
  configuration resources and ownership; this ticket covers filesystem parent
  directories required by link artifacts.

## What probably needs to be done

- Add an explicit managed-directory operation with required mode and ownership.
- Journal whether each directory existed before the transaction and the exact
  identity of a directory created by MAINFRAME.
- Create path components descriptor-relatively without following symbolic
  links, syncing every new parent entry.
- Roll back only an exact MAINFRAME-created directory that is still empty;
  otherwise retain it and report a warning or conflict.
- Make link operations depend on their required directory operations.

## Acceptance criteria

- A first install can create every missing target root without implicit writes
  inside the link workspace.
- Interruption after every directory creation boundary is recoverable.
- Rollback never removes a pre-existing, replaced, non-empty, or foreign
  directory.
- Modes and ownership are verified on macOS and Linux fixtures.
- Tier-1 tests cover nested creation, partial pre-existence, concurrent
  population, symlink substitution, rollback, and idempotent retry.

## Sources

- `internal/executor/types.go`
- `internal/hostlayout/layout.go`
- `internal/releasecontract/types.go`
- `docs/tickets/7a1c1d1d-add-safe-plan-application.md`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`
