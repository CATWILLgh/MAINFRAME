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
OpenCode permission actions through their separate ownership registry, and
Codex global user-hook trust through Codex's own `hooks/list` interface.
OpenCode, Claude Code, Codex, and Antigravity MCP now have separate release-owned
projections, read-only ownership plans, and exact private preparation paths.
All four can prepare adapter-local file mutations without writing, while none
of the MCP paths can be applied from the CLI or TUI.

## Why it is a problem

The TUI can now explain generic selected-resource changes and detailed
OpenCode permission intent, but it still cannot build a safe removal plan for
every behavior handled by `install.sh` and adapter-specific generators.
Comparing entire JSON files would overwrite or misclassify user-owned keys.
Codex hook file presence also cannot prove that its definitions are enabled
and trusted.

## Why it is not a duplicate

[#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) covers journaling, backup, recovery, and execution of an already valid plan. This ticket defines the ownership-aware configuration state and operations that such a plan must contain. [#06cb98c8](06cb98c8-publish-opencode-config-and-ownership-consistently.md) covers atomic publication in the existing OpenCode writer, not the cross-adapter release contract.

## What probably needs to be done

- Represent each adapter's MCP additions and ownership independently from other adapters and configuration resources.
- Complete removal and application contracts for every configuration strategy
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
- One immutable inspection now drives both status and a deterministic semantic
  plan. The TUI distinguishes add, update, registry-proven removal, and
  stopping management of user-changed or deleted OpenCode actions without
  exposing raw bytes or executable configuration operations.
- The same inspection can now prepare exact, immutable OpenCode configuration
  and registry after-images without writing. Preparation preserves ordered
  user JSON, coalesces shared physical targets, binds existing files by digest,
  mode, device, and inode, and fails closed for every unsupported change.
- The executor can now apply a supported prepared transition, including
  registry-proven removal, as one recoverable journaled transaction across the
  configuration and ownership files.
- Codex hook trust now has a typed adapter-local external-state descriptor.
  Observation uses the bounded read-only `hooks/list` protocol, requires an
  exact non-empty desired handler set and managed-exact hook artifact, and
  fails closed for disabled, untrusted, modified, partial, unexpected,
  malformed, or unavailable state. MAINFRAME does not read or write
  `hooks.state`.
- The semantic plan separates manual actions and external notices from
  executable changes and blocking ownership issues. They never enter prepared
  transitions or journals, and deselection neither reports nor revokes them.
- OpenCode keyless Context7 now has an independent schema-v2 projection,
  adapter-local shared MCP registry, exact-key reconciliation, catalog-derived
  desired value, and a semantic-only TUI plan. Generic and MCP observation use
  one immutable per-location snapshot. OpenCode MCP can now prepare ordered
  JSON and registry after-images, including add, update, removal, relinquish,
  and several entries sharing one target and registry. When permissions and
  MCP both change `opencode.json`, exact before-image equality and disjoint
  release-owned pointers produce one transition without overwriting either
  result. Apply remains unavailable.
- Claude Code keyless Context7 now has its own schema-v2 codec for the exact
  user-scope `~/.claude.json` `mcpServers.context7` entry. Its ownership registry
  is under `~/.claude/mainframe/`, it does not grant the Claude component broad
  home-root access, and loaded values are revalidated before host reads. The
  same immutable inspection can now prepare ordered `.claude.json` and registry
  after-images for add, update, removal, relinquishment, and several servers.
  Unrelated preferences and sibling adapters remain isolated, and Apply stays
  unavailable.
- Antigravity keyless Context7 now has an exact schema-v2 projection for the
  canonical global `~/.gemini/config/mcp_config.json`
  `mcpServers.context7` entry. It derives the adapter-native `serverUrl` value
  from the verified catalog, keeps ownership under Antigravity's own data root,
  and privately prepares add, update, removal, relinquishment, and ready states
  without touching sibling servers or unknown fields. Legacy-path detection and
  migration remain a prerequisite tracked in
  [#cd0cdc27](cd0cdc27-detect-legacy-antigravity-mcp-config.md); Apply stays
  unavailable.
- Codex keyless Context7 now has an exact adapter-local projection for
  `config.toml` `mcp_servers.context7`. A strict TOML parser observes only that
  selected table, its registry remains JSON under the Codex configuration
  root, and non-JSON TOML semantics trigger safe relinquishment instead of
  lossy comparison. Release validation rejects mixed JSON and TOML ownership
  on one physical target.
- Codex keyless Context7 can now prepare exact `config.toml` and adapter-local
  registry after-images from one immutable snapshot. It owns only a
  versioned, registry-proven suffix block, validates full TOML semantics around
  every change, preserves unrelated bytes, and fails closed on legacy or
  edited block provenance. The prepared transition composes with generic
  configuration for the existing recoverable executor, while Apply remains
  absent from the CLI and TUI.
- The single-entry Codex block format rejects a second Codex MCP projection.
  A deterministic multi-entry managed region is tracked separately in
  [#38b9fb12](38b9fb12-compose-codex-mcp-managed-region.md).
- Combined MCP plans retain every selected adapter's intent while remaining
  blocking if any adapter conflicts. Unselected sibling state is ignored.
- Apply remains unavailable. Antigravity legacy-path migration and other
  strategies still need safe deselection semantics.

## Acceptance criteria

- Every configuration behavior currently performed by the legacy installer or an adapter generator is represented once in the release contract or explicitly classified as an external prerequisite.
- JSON observation reports drift only for MAINFRAME-owned keys and preserves unrelated user content.
- Claude Code MCP, Codex MCP, OpenCode MCP, Antigravity MCP, and OpenCode
  permission ownership can be planned independently.
- Codex trust is never reported ready from file presence alone.
- Tier 1 tests cover add, update, remove, user override, malformed input, and adapter isolation for each supported strategy.

## Sources

- `internal/releasecontract/types.go`
- `internal/releasecontract/json_map_ownership.go`
- `internal/jsondocument/document.go`
- `internal/configuration/observer.go`
- `internal/configuration/inspection.go`
- `internal/configuration/planner.go`
- `internal/configuration/prepared.go`
- `internal/configuration/owned_map.go`
- `internal/codexstate/observer.go`
- `internal/codexstate/app_server.go`
- `internal/executor/configuration_execute.go`
- `internal/executor/configuration_recovery.go`
- `internal/lifecycle/configuration_preview.go`
- `internal/mcpconfiguration/inspection.go`
- `internal/mcpconfiguration/planner.go`
- `internal/mcpconfiguration/json_config.go`
- `adapters/antigravity-2/build_bundle.py`
- `internal/releasecontract/mcp_projection.go`
- `cmd/mainframe/inspection_cache.go`
- `adapters/claude-code/build_bundle.py`
- `adapters/opencode/build_bundle.py`
- `adapters/opencode/build_opencode.py`
- `adapters/codex/build_bundle.py`
- <https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#hooks>
- `docs/tickets/7a1c1d1d-add-safe-plan-application.md`
- `docs/tickets/06cb98c8-publish-opencode-config-and-ownership-consistently.md`

## Re-occurrence noted (2026-07-17)

**Noticed during:** keyless Context7 semantic configuration planning
**Where:** `internal/mcpconfiguration`, bundle schema v2, and adapter builders
**Additional details:** OpenCode and Claude Code can produce exact read-only
`add`/`update`/`remove`/`relinquish`/`conflict` intent without exposing file
bytes in the TUI. OpenCode, Claude Code, and Codex also have private preparation
paths, but no MCP execution path. Their codecs and registries are independent.
Completing the same capability for the other adapters requires their own roots
and codecs rather than reading or reusing another adapter's state.
