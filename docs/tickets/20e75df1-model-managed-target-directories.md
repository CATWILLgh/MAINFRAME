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

- Run the lifecycle fixtures natively on Linux. Linux compilation is covered,
  but compilation does not exercise filesystem rename and durability behavior.
- Keep Apply unavailable until that check and the remaining executor gates in
  [#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) pass.

## Acceptance criteria

- A first install can create every missing target root without implicit writes
  inside the link workspace.
- Interruption after every directory creation boundary is recoverable.
- Rollback never removes a pre-existing, replaced, non-empty, or foreign
  directory.
- Modes and ownership are verified on macOS and Linux fixtures.
- Tier-1 tests cover nested creation, partial pre-existence, concurrent
  population, symlink substitution, rollback, and idempotent retry.

## Progress (2026-07-16)

- Added explicit ordered directory actions to the transaction journal together
  with the original plan and canonical root snapshots.
- Added pure allowed-path derivation, physical alias deduplication, physical
  link-target conflict rejection, and strict cross-collection validation.
- Added lazy configured roots so a workspace can open before `~/.local/bin`,
  `~/.codex`, or nested adapter parents exist.
- Added descriptor-relative staging, no-replace publication, exact identity and
  mode checks, parent-first application, and child-first rollback after links.
- Added recovery for every journal boundary, including a failed restoration
  caused by a concurrently occupied public name. Populated directories are
  retained and restored, never removed.
- Bound recovery snapshots back to the currently configured physical roots
  before any mutation and repeated the check inside each filesystem operation.
- Added native Darwin tests for nested and partially existing paths, symbolic
  link substitution, physical aliases, no-replace publication, interruption,
  concurrent population, restoration retry, and end-to-end first installation.
- Defined `0700` as the same-user policy for every newly created managed
  directory while preserving every existing directory's mode. No current
  runtime requires cross-user traversal, so root-specific numeric modes would
  not represent a real access boundary.
- Added coverage for a process mask that removes owner permission bits and
  rejects it before managed-directory intent persistence or target-directory
  mutation. The check reads the inherited mask in an isolated child process and
  never changes the installer's mask.
- Added race-detector coverage and Linux cross-compilation. Native Linux
  lifecycle execution remains open.

## Sources

- [XDG Base Directory Specification 0.8](https://specifications.freedesktop.org/basedir/latest/)
- `internal/executor/types.go`
- `internal/hostlayout/layout.go`
- `internal/releasecontract/types.go`
- `docs/tickets/7a1c1d1d-add-safe-plan-application.md`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`
