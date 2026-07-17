---
id: cd0cdc27
title: Detect and migrate the legacy Antigravity MCP configuration
status: open
priority: medium
component: installer-antigravity
discovered: 2026-07-17
discovered-from: ["#cd5f584d"]
tags: ["antigravity", "mcp", "migration", "tui", "configuration"]
---

# cd0cdc27: Detect and migrate the legacy Antigravity MCP configuration

## What was observed

Current Antigravity documentation places the global MCP configuration at
`~/.gemini/config/mcp_config.json`. Other current official Google documentation
still names `~/.gemini/antigravity/mcp_config.json`, and both files exist on the
verified Antigravity 2.2.1 development host. The installer now observes both
locations but writes neither during migration detection.

## Why it is a problem

Detection and privacy-safe preview are implemented, but official sources do not
define version boundaries, simultaneous loading, or precedence. Automatic
migration or deletion would therefore risk choosing the wrong source of truth.
That behavior must remain unavailable until it is verified against supported
Antigravity versions.

## Why it is not a duplicate

- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) tracks the
  complete configuration execution lifecycle. This ticket owns the narrower
  Antigravity legacy-path detection, precedence, and migration contract that
  lifecycle must call before publication.

## What probably needs to be done

Completed in the installer branch:

- Both locations are inspected once through immutable snapshots.
- Preview exposes fixed, credential-free states for legacy-only, canonical-only,
  equivalent dual, conflicting dual, and invalid legacy configuration.
- Material Antigravity MCP preparation is rejected while migration is required;
  unrelated Antigravity preparation remains available.

Remaining work:

1. Verify which supported Antigravity versions read each path and their runtime
   precedence when both exist.
2. Define an explicit user choice and safe mutation contract for migration,
   including deletion support in the configuration executor.
3. Preserve unrelated servers and unknown fields during the chosen migration.
4. Keep Antigravity MCP Apply gated until the mutation contract and live checks
   are complete.

## Acceptance criteria

- [x] Tier 1 tests cover legacy-only, canonical-only, equivalent, conflicting,
  invalid, unreadable, symbolic-link, and non-regular states.
- [x] Preview reports legacy presence without exposing configuration values.
- [x] Preparation cannot silently create a second active definition while
  legacy state is unresolved.
- [ ] Migration preserves unrelated servers and unknown fields.
- [ ] Live verification records behavior and precedence on every supported
  Antigravity major line.

## Re-occurrence noted (2026-07-17)

**Noticed during:** Antigravity MCP configuration preparation for the installer TUI
**Where:** `internal/mcpconfiguration/antigravity_legacy.go` and
`internal/tui/mcp_preview.go`
**Additional details:** Detection, semantic comparison, privacy-safe preview, and
the preparation gate are implemented. Runtime precedence, user-directed
migration, file deletion, and live version checks remain deliberately deferred;
the ticket stays open for those boundaries.

## Sources

- `internal/mcpconfiguration/inspection.go:48-95`
- `internal/mcpconfiguration/antigravity_legacy.go`
- `internal/tui/mcp_preview.go`
- `internal/hostlayout/layout.go:55-63`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`
- [Antigravity MCP documentation](https://antigravity.google/docs/mcp)
- [Google Workspace Sheets MCP guide](https://developers.google.com/workspace/sheets/api/guides/configure-mcp-server)
- [Antigravity Gemini CLI migration](https://antigravity.google/docs/gcli-migration)
