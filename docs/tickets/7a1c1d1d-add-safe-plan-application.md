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

The final product must install, update, remove, and replace selected adapters. Adding a confirmation button without an executor that revalidates ownership, journals operations, backs up conflicts, and recovers after interruption would turn a safe preview into an unsafe installer.

## Why it is not a duplicate

[#40f67f95](40f67f95-complete-release-manifest-for-tui.md) covers the completeness and location of release inputs. This ticket covers mutating execution after a complete plan already exists.

## What probably needs to be done

- Define write operations behind a narrow executor interface outside the TUI.
- Re-discover and revalidate every affected artifact immediately before mutation.
- Journal operation start and completion, create protected backups, and support idempotent continuation or recovery.
- Add a separate confirmation screen that displays the exact final plan and blocks on unresolved conflicts.
- Exercise interruption after each operation on macOS and Linux fixtures before enabling Apply.

## Acceptance criteria

- The TUI owns no direct filesystem, process, network, or package-manager writes.
- Only `managed_exact` artifacts can be removed automatically; drifted, foreign, legacy-adoptable, and conflicting artifacts stop for a decision.
- An interrupted operation can be continued or restored without losing user data.
- Repeated application of the same desired state is idempotent.
- macOS and Linux lifecycle fixtures cover install, add, remove, replace, conflict, interruption, and recovery.
- Apply remains unavailable until the full release-manifest ticket is complete and independently audited.

## Sources

- `internal/tui/model.go:52`
- `internal/plan/planner.go:19`
- `internal/domain/types.go:68`
