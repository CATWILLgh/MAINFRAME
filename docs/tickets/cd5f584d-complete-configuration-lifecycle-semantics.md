---
id: cd5f584d
title: Complete ownership-aware configuration lifecycle semantics
status: open
priority: medium
component: installer
discovered: 2026-07-15
discovered-from: ["#7a1c1d1d"]
tags: ["tui", "configuration", "ownership", "opencode", "codex"]
---

# cd5f584d: Complete ownership-aware configuration lifecycle semantics

## What was observed

The read-only observer can safely classify seed-if-absent files, required or
optional shell lines, directories, the three Claude Code permission arrays,
and OpenCode permission actions through their separate ownership registry.
Codex hook trust remains explicitly not assessed because it is external
project state. OpenCode MCP projection is not represented as a release resource
and has no ownership registry.

## Why it is a problem

The TUI cannot yet explain configuration drift or build a safe configuration plan for all behavior currently handled by `install.sh` and adapter-specific generators. Comparing entire JSON files would overwrite or misclassify user-owned keys, while file presence cannot prove Codex project trust.

## Why it is not a duplicate

[#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) covers journaling, backup, recovery, and execution of an already valid plan. This ticket defines the ownership-aware configuration state and operations that such a plan must contain. [#06cb98c8](06cb98c8-publish-opencode-config-and-ownership-consistently.md) covers atomic publication in the existing OpenCode writer, not the cross-adapter release contract.

## What probably needs to be done

- Represent OpenCode MCP additions and their ownership independently from permission rules.
- Model Codex hook trust as adapter-local external state instead of inferring it from `hooks.json`.
- Define plan, apply, and removal contracts for each configuration strategy
  before exposing an Apply action.
- Prove that each adapter reads and writes only its own configuration and state projections.

## Progress

- Claude Code observation owns only `/permissions/allow`, `/permissions/ask`, and `/permissions/deny` through strict RFC 6901 pointers.
- The release contract rejects ambiguous JSON, overlapping ownership, install-target collisions, and source bytes that do not match the payload inventory.
- The observer reads each JSON target once, ignores unrelated user keys, and distinguishes drift from malformed structure.
- OpenCode permissions now declare a versioned map-entry ownership descriptor
  with an adapter-local registry. The observer preserves scalar overrides,
  tombstones, user changes, deletions, wildcard conflicts, and nested rule
  ordering according to the same semantics as the compatibility generator.
- Apply and removal remain unavailable. OpenCode still needs journaled two-file
  publication and independent MCP ownership; Codex still needs an
  adapter-local external trust contract.

## Acceptance criteria

- Every configuration behavior currently performed by the legacy installer or an adapter generator is represented once in the release contract or explicitly classified as an external prerequisite.
- JSON observation reports drift only for MAINFRAME-owned keys and preserves unrelated user content.
- OpenCode MCP and permission ownership can be installed, updated, and removed independently.
- Codex trust is never reported ready from file presence alone.
- Tier 1 tests cover add, update, remove, user override, malformed input, and adapter isolation for each supported strategy.

## Sources

- `internal/releasecontract/types.go`
- `internal/releasecontract/json_map_ownership.go`
- `internal/jsondocument/document.go`
- `internal/configuration/observer.go`
- `internal/configuration/owned_map.go`
- `adapters/claude-code/build_bundle.py`
- `adapters/opencode/build_bundle.py`
- `adapters/opencode/build_opencode.py`
- `adapters/codex/build_bundle.py`
- `docs/tickets/7a1c1d1d-add-safe-plan-application.md`
- `docs/tickets/06cb98c8-publish-opencode-config-and-ownership-consistently.md`
