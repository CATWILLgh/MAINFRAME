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

The read-only observer can safely classify seed-if-absent files, required or optional shell lines, and directories. Claude Code settings, OpenCode permission configuration, and Codex hook trust remain explicitly not assessed because their owned subsets and external state are not encoded in the release contract. OpenCode MCP projection is not represented as a release resource at all.

## Why it is a problem

The TUI cannot yet explain configuration drift or build a safe configuration plan for all behavior currently handled by `install.sh` and adapter-specific generators. Comparing entire JSON files would overwrite or misclassify user-owned keys, while file presence cannot prove Codex project trust.

## Why it is not a duplicate

[#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) covers journaling, backup, recovery, and execution of an already valid plan. This ticket defines the ownership-aware configuration state and operations that such a plan must contain. [#06cb98c8](06cb98c8-publish-opencode-config-and-ownership-consistently.md) covers atomic publication in the existing OpenCode writer, not the cross-adapter release contract.

## What probably needs to be done

- Encode owned JSON paths and merge semantics without treating user-owned keys as MAINFRAME state.
- Represent OpenCode MCP additions and their ownership independently from permission rules.
- Model Codex hook trust as adapter-local external state instead of inferring it from `hooks.json`.
- Define observable, plan, apply, and removal contracts for each configuration strategy before exposing an Apply action.
- Prove that each adapter reads and writes only its own configuration and state projections.

## Acceptance criteria

- Every configuration behavior currently performed by the legacy installer or an adapter generator is represented once in the release contract or explicitly classified as an external prerequisite.
- JSON observation reports drift only for MAINFRAME-owned keys and preserves unrelated user content.
- OpenCode MCP and permission ownership can be installed, updated, and removed independently.
- Codex trust is never reported ready from file presence alone.
- Tier 1 tests cover add, update, remove, user override, malformed input, and adapter isolation for each supported strategy.

## Sources

- `internal/releasecontract/types.go`
- `internal/configuration/observer.go`
- `adapters/claude-code/build_bundle.py`
- `adapters/opencode/build_bundle.py`
- `adapters/opencode/build_opencode.py`
- `adapters/codex/build_bundle.py`
- `docs/tickets/7a1c1d1d-add-safe-plan-application.md`
- `docs/tickets/06cb98c8-publish-opencode-config-and-ownership-consistently.md`
