---
id: 7a1c1d1d
title: Add recoverable plan application after the read-only TUI is complete
status: open
priority: medium
component: installer
discovered: 2026-07-15
discovered-from: []
tags: ["tui", "executor", "recovery", "ownership"]
---

# 7a1c1d1d: Add recoverable plan application after the read-only TUI is complete

## What was observed

The first terminal interface intentionally supports selection, plan preview, Back, and Quit only. It has no Apply action and no write-capable dependency. This preserves the agreed safety boundary while bundle inventory and release delivery remain incomplete.

## Why it is a problem

The final product must install, update, remove, and replace selected adapters. Adding a confirmation button without an executor that revalidates ownership, rejects conflicts, journals operations, and recovers after interruption would turn a safe preview into an unsafe installer.

## Why it is not a duplicate

[#40f67f95](40f67f95-complete-release-manifest-for-tui.md) covers the completeness and location of release inputs. This ticket covers mutating execution after a complete plan already exists.

## What probably needs to be done

- Keep write operations behind the narrow executor interface outside the TUI.
- Connect the executor to a fresh release load, discovery, and plan rebuild while
  holding the transaction lock.
- Complete immutable release publication and publisher authentication before
  installed links can target downloaded payloads.
- Complete configuration ownership and application semantics.
- Model creation and rollback of missing managed target directories before
  first-install plans may apply link operations.
- Add a separate confirmation screen that displays the exact final plan and blocks on unresolved conflicts.
- Exercise interruption after each operation on macOS and Linux fixtures before enabling Apply.

## Acceptance criteria

- The TUI owns no direct filesystem, process, network, or package-manager writes.
- Only `managed_exact` artifacts can be removed automatically; drifted, foreign, legacy-adoptable, and conflicting artifacts stop for a decision.
- An interrupted operation can be continued or restored without losing user data.
- Repeated application of the same desired state is idempotent.
- macOS and Linux lifecycle fixtures cover install, add, remove, replace, conflict, interruption, and recovery.
- TUI execution and `install.sh` cannot mutate managed links concurrently.
- Apply remains unavailable until release authenticity, immutable publication,
  configuration lifecycle, and cross-platform executor checks pass independent
  review.

## Progress (2026-07-16)

- Added an internal executor with exact release-index digest and fresh-plan
  equality checks.
- Added exclusive process locking, a private atomically published journal,
  reverse rollback, interruption recovery, and cleanup retry.
- Added inode-aware before/after images so rollback refuses a same-target link
  that was replaced after publication.
- Added a complete-release store keyed by release ID and exact index digest,
  with closed-tree validation, descriptor-relative copying, locking, durable
  staging, and Darwin/Linux no-replace publication.
- Documented that stored releases remain mutable by another same-user process;
  future planning and application must revalidate them immediately before use.
- Added a Darwin/Linux link workspace that opens paths descriptor-relatively,
  rejects symbolic-link traversal, pins directory and link identities, and
  publishes with platform-native no-replace renames.
- Reworked installation and removal so the public name is never unlinked:
  installation renames a journaled staged link into place, while removal
  retains the original link inode in a journaled private directory until
  commit or rollback.
- Added retryable recovery for private-directory creation, staging,
  publication, rollback, committed finalization, and journal cleanup, including
  a real executor/workspace compatibility test.
- Made the commit boundary monotonic: once persisting `committed` is attempted,
  an uncertain save result is left for recovery and the current process never
  starts rollback.
- Made every mutating compatibility-installer path share the Go executor's
  persistent transaction lock. The installer uses macOS `lockf` or Linux
  `flock`, fails closed on contention, preserves source-preflight and dry-run
  read-only behavior, and never removes the lock file.
- Added cross-process compatibility coverage proving the platform utility
  cannot enter while Go holds the lock, plus install/uninstall ordering,
  contention, release, path, ownership, and mode coverage.
- Tightened the planner so removal requires both `managed_exact` ownership and
  a matching artifact declared by the same release component.
- Added an explicit recoverable managed-directory lifecycle. Missing roots and
  nested parents are journaled before writes, created before links, bound to
  configured physical roots and exact identities, and rolled back child-first
  without deleting populated or foreign directories.
- Added pure configuration transaction preparation. It composes ordered JSON
  changes per physical target, groups OpenCode configuration with its ownership
  registry, and binds every existing before-image by content digest, mode,
  device, and inode without writing or placing secret bytes in the journal.
- Kept CLI and TUI application unavailable. Remaining activation gates are
  tracked by [#d3b15da9](d3b15da9-authenticate-release-publisher.md),
  [#66ab4af8](66ab4af8-make-bundle-publication-atomic.md),
  [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md), and
  [#33930a3b](33930a3b-enable-selective-release-downloads.md). The managed
  directory mode policy is resolved; native Linux lifecycle verification
  remains tracked in
  [#20e75df1](20e75df1-model-managed-target-directories.md).

## Sources

- `internal/tui/model.go:52`
- `internal/plan/planner.go:19`
- `internal/executor/executor.go`
- `internal/configuration/prepared.go`
- `internal/executor/locker_compatibility_unix_test.go`
- `internal/linkworkspace/workspace_unix.go`
- `tools/test_install_lock.py`
