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
still names `~/.gemini/antigravity/mcp_config.json`. A live check against
Antigravity 2.2.1 confirmed that a synthetic MCP command from the canonical path
is executed and that the equivalent command from a regular file present only at
the legacy path is not executed. The installer observes both locations but
writes neither during migration detection.

## Why it is a problem

Detection and privacy-safe preview are implemented, but official sources do not
define version boundaries or precedence. Live checks now show that only
canonical-path synthetic MCP commands execute on 2.2.1 when both paths are valid
regular files, whether server keys collide or differ. Automatic migration or
deletion would still risk choosing the wrong source of truth on other supported
versions, so that behavior must remain unavailable until the supported-version
policy is explicit.

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

1. Verify the remaining supported Antigravity versions or narrow the supported
   runtime policy to versions with proven canonical command precedence.
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
- [x] Antigravity 2.2.1 live verification confirms canonical-only command
  execution and no legacy-only command execution during the probe.
- [x] Antigravity 2.2.1 live verification confirms canonical precedence when
  both paths define the same MCP server key.
- [x] Antigravity 2.2.1 live verification confirms that a synthetic command for
  a distinct legacy-only server key does not execute alongside the canonical
  command.
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

## Live verification (2026-07-17)

**Version:** Antigravity 2.2.1 (`com.google.antigravity`)

**Method:** The existing credential-bearing configuration was moved into a
private same-filesystem backup and never launched. Each candidate path was then
tested with a distinct synthetic MCP entry whose only command created an empty
private marker. Two launches with both paths absent guarded against cached
execution. The application was fully stopped between cases, and the original
file, permissions, ownership, inode, content hash, and legacy symbolic link were
verified after restoration.

**Observed:**

- Neither-path control: no synthetic command was launched.
- Canonical-only regular file at `~/.gemini/config/mcp_config.json`: the distinct
  synthetic command was launched.
- Second neither-path control: no cached synthetic command was launched.
- Legacy-only regular file at `~/.gemini/antigravity/mcp_config.json`: the
  distinct synthetic command was not launched.
- Simultaneous regular files with the same server key and different synthetic
  commands: only the canonical-path command was launched.
- A second absent-path launch after the simultaneous case launched neither
  command, excluding cached execution as the source of the result.
- Simultaneous regular files with different server keys and different synthetic
  commands: only the canonical-path command was launched; the command for the
  legacy-only key did not execute alongside it.
- A post-case absent-path launch after the distinct-key check launched neither
  command, again excluding cached execution.
- Antigravity created a canonical-path file even during absent-path controls, so
  canonical file creation alone is not evidence of legacy migration.
- Original state was restored exactly; Antigravity was stopped and all probe
  artifacts were removed.

This establishes canonical-only synthetic MCP command execution for the tested
Antigravity 2.2.1 cases when both paths are valid regular files: same-key command
execution resolves to canonical, and a distinct legacy-key command does not
execute alongside the canonical command. It does not establish whether the
legacy file is read or parsed, behavior for non-synthetic entries or other file
shapes, or behavior on other versions. Automatic migration remains gated.

## Sources

- `internal/mcpconfiguration/inspection.go:48-95`
- `internal/mcpconfiguration/antigravity_legacy.go`
- `internal/tui/mcp_preview.go`
- `internal/hostlayout/layout.go:55-63`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`
- [Antigravity MCP documentation](https://antigravity.google/docs/mcp)
- [Antigravity changelog](https://antigravity.google/changelog?app=antigravity)
- [Google Workspace Sheets MCP guide](https://developers.google.com/workspace/sheets/api/guides/configure-mcp-server)
- [Antigravity Gemini CLI migration](https://antigravity.google/docs/gcli-migration)
