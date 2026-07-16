---
id: 06cb98c8
title: Publish OpenCode configuration and permission ownership consistently
status: open
priority: medium
component: opencode
discovered: 2026-07-15
discovered-from: []
tags: ["permissions", "ownership", "recovery", "atomicity"]
---

# 06cb98c8: Publish OpenCode configuration and permission ownership consistently

## What was observed

`build_opencode.py` publishes `opencode.json` before it publishes the permission-ownership state. If the second write fails, the new generated rules remain in the user configuration while the ownership file is missing or stale. The next run treats those rules as user-owned and will no longer update or remove them.

## Why it is a problem

The configuration and its ownership registry form one logical state transition but currently have two independent publication points. Reordering them only reverses the inconsistency: a state-first failure can claim ownership of rules that were never published.

## Why it is not a duplicate

[#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) covers the future TUI executor and filesystem lifecycle. This ticket covers the existing OpenCode configuration writer and its separate ownership registry.

## What probably needs to be done

- Define a recoverable two-file publication protocol or journal for configuration and ownership state.
- Detect and reconcile an interrupted transition on the next run.
- Preserve user changes and existing backup guarantees through every failure point.
- Avoid treating an uncommitted generated action as user-owned after recovery.

## Acceptance criteria

- Failure before or after either file publication converges on the next run without losing user policy.
- Generated actions remain updatable and removable after an interrupted publication.
- User-owned actions are never adopted or overwritten during recovery.
- Failure-injection tests cover both publication orders and every recovery branch.

## Progress

- The release contract now models `opencode.json` and its permission registry
  as one versioned ownership relationship.
- Read-only observation detects a missing, stale, malformed, or inconsistent
  registry without adopting user entries.
- Read-only planning groups the configuration and registry as one semantic
  transition and removes only entries whose active ownership is still proven.
- Pure preparation now materializes exact ordered after-images for both files
  in one transition and binds their before-images by digest, mode, device, and
  inode without writing.
- The Go executor now stages prepared bytes in identity-bound private
  workspaces, journals both files by digest and inode without storing their
  contents, publishes each boundary atomically, and rolls the logical
  transition back in reverse order after interruption.
- The compatibility Python writer remains sequential and does not use this
  protocol. This ticket therefore remains open until that path is migrated or
  retired and its failure-injection acceptance criteria pass.

## Sources

- `adapters/opencode/build_opencode.py:344`
- `adapters/opencode/permission_config.py:87`
- `adapters/opencode/config_writer.py:173`
- `internal/configuration/owned_map_observer.go`
- `internal/configuration/planner.go`
- `internal/configuration/prepared.go`
- `internal/executor/configuration_execute.go`
- `internal/executor/configuration_recovery.go`
- `internal/linkworkspace/configuration_publish_unix.go`
- `internal/releasecontract/json_map_ownership.go`
- `tools/test_opencode_config_writer_failures.py`
