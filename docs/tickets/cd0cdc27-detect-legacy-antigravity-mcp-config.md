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

Antigravity 2.0 is the standalone desktop product targeted by this adapter; it is
separate from Antigravity IDE. The official Antigravity 2.0 documentation names
`~/.gemini/antigravity` as its runtime root and `~/.gemini/config` as the shared
customization root. Its product-specific MCP section describes configuration
through the application interface but does not publish a raw global MCP filename.
On the verified standalone Antigravity 2.2.1 host,
`~/.gemini/antigravity/mcp_config.json` is a direct symbolic link to
`~/.gemini/config/mcp_config.json`, so the two paths identify one configuration
rather than two independent files. A live check on that host also confirmed that
a synthetic MCP command from the latter path is executed and that the equivalent
command from a standalone regular file present only at the former path is not
executed.

The terms “canonical”, “noncanonical”, and “legacy” in this ticket are MAINFRAME
classification terms, not names assigned to these paths by the product vendor.

## Why it is a problem

The installer originally classified every symbolic link at the noncanonical
path as an invalid legacy configuration. That creates a false conflict when the
link points directly to the independently inspected canonical regular file.
Standalone files at the noncanonical path remain unresolved: the Antigravity 2.0
documentation does not define that file or its migration semantics, and automatic
migration or deletion could still activate or destroy user-owned data.

## Why it is not a duplicate

- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) tracks the
  complete configuration execution lifecycle. This ticket owns the narrower
  Antigravity legacy-path detection, precedence, and migration contract that
  lifecycle must call before publication.

## What probably needs to be done

Completed in the installer branch:

- Both locations are inspected once through immutable snapshots.
- A direct alias to the independently inspected canonical regular file is
  classified as canonical-only; foreign, unresolved, or unsafe links remain
  invalid.
- Material changes carry the alias identity and exact target as a read-only
  transaction precondition; a replacement after preview aborts before journaling
  or filesystem writes.
- Preview exposes fixed, credential-free states for legacy-only, canonical-only,
  equivalent dual, conflicting dual, and invalid legacy configuration.
- Material Antigravity MCP preparation is rejected while migration is required;
  unrelated Antigravity preparation remains available.
- TUI host discovery enforces the exact managed Antigravity `2.2.1` requirement,
  explains unavailable states, and preserves an already installed incompatible
  adapter without repair or removal. The legacy installer retains its broader
  2.x policy.

Remaining work:

1. Define an explicit user choice and safe mutation contract for migration,
   including deletion support in the configuration executor.
2. Preserve unrelated servers and unknown fields during the chosen migration.
3. Keep Antigravity MCP Apply gated until the mutation contract and live checks
   are complete.

## Acceptance criteria

- [x] Tier 1 tests cover legacy-only, canonical-only, equivalent, conflicting,
  invalid, unreadable, symbolic-link, and non-regular states.
- [x] Tier 1 tests distinguish an exact canonical alias from foreign or
  unresolved symbolic links without following the link.
- [x] Applying a prepared material change revalidates the alias before any
  persistent transaction state or configuration write.
- [x] Preview reports legacy presence without exposing configuration values.
- [x] Preparation cannot silently create a second active definition while
  legacy state is unresolved.
- [x] TUI host discovery enforces the exact managed version without blocking
  unrelated adapters or removing an already installed incompatible adapter.
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

**Version:** standalone Antigravity 2.2.1 (`com.google.antigravity`)

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
standalone Antigravity 2.2.1 cases when both paths are valid regular files:
same-key command execution resolves to canonical, and a distinct legacy-key
command does not execute alongside the canonical command. The raw filename is an
observed compatibility contract for this exact supported host, not a guarantee
imported from Antigravity IDE. The check does not establish whether the legacy
file is read or parsed, behavior for non-synthetic entries or other file shapes,
or behavior on other versions. Automatic migration remains gated.

## Sources

- `internal/mcpconfiguration/inspection.go:48-95`
- `internal/mcpconfiguration/antigravity_legacy.go`
- `internal/tui/mcp_preview.go`
- `internal/hostlayout/layout.go:55-63`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`
- [Introducing Google Antigravity 2](https://antigravity.google/blog/introducing-google-antigravity-2?hl=en)
- [Antigravity 2.0 overview](https://antigravity.google/docs/overview?hl=en)
- [Antigravity hooks documentation](https://antigravity.google/docs/hooks)
- [Antigravity MCP documentation](https://antigravity.google/docs/mcp)
- [Antigravity changelog](https://antigravity.google/changelog?app=antigravity)
