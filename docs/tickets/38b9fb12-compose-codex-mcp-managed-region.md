---
id: 38b9fb12
title: Compose multiple Codex MCP entries in one managed TOML region
status: open
priority: medium
component: installer
discovered: 2026-07-17
discovered-from: ["#cd5f584d"]
tags: ["tui", "codex", "mcp", "toml", "ownership"]
---

# 38b9fb12: Compose multiple Codex MCP entries in one managed TOML region

## What was observed

Codex MCP preparation recognizes one versioned, registry-proven managed block
as an exact suffix of `config.toml`. This is safe for the current release,
whose catalog exposes only Context7, but separate suffix blocks would not
scale: after a second server block is appended, the first block is no longer
the exact file suffix and cannot be updated or removed safely.

## Why it is a problem

The MCP catalog is intended to grow. Adding another Codex-compatible server
without first changing the ownership format would either block later updates
or tempt an unsafe non-suffix search through user-controlled TOML. The latter
can collide with identical text inside multiline strings.

## Why it is not a duplicate

- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) tracks the complete cross-adapter configuration lifecycle. This ticket isolates the Codex-specific multi-entry byte-ownership format required before a second server projection can ship.

## What probably needs to be done

- Replace per-entry suffix blocks with one deterministic, versioned managed
  region at the end of `config.toml`.
- Render all registry-proven Codex entries in sorted server order and replace
  the region atomically when any member changes.
- Bind registry provenance to the region format and validate complete TOML
  semantics before and after every change.
- Reject a release containing more than one Codex MCP projection until this
  region format is implemented and migration behavior is specified.

## Acceptance criteria

- Two or more Codex MCP servers can be added, updated, removed, and relinquished independently without changing bytes outside the managed region.
- Reordering catalog records does not change the rendered region.
- A marker-like multiline string cannot be mistaken for the managed region.
- Removing the final managed entry restores all pre-existing TOML bytes.
- Release validation prevents multiple Codex MCP projections while the single-entry format remains active.

## Sources

- `internal/mcpconfiguration/codex_toml.go`
- `internal/mcpconfiguration/prepared.go`
- `internal/releasecontract/mcp_projection.go`
- `internal/mcpcatalog/catalog.json`
- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md)
- <https://toml.io/en/v1.0.0>
