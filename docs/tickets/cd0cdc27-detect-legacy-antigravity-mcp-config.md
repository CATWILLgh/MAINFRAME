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
`~/.gemini/config/mcp_config.json`. Older official documentation used
`~/.gemini/antigravity/mcp_config.json`, and both files exist on the verified
Antigravity 2.2.1 development host. The installer projection observes only the
current canonical target.

## Why it is a problem

A user with only the legacy file can appear to have no configured MCP server.
The TUI could then propose a canonical addition without explaining that an old
configuration exists. This is safe while preparation cannot be applied, but it
must be resolved before Apply is enabled to avoid ambiguous migration and
duplicate configuration behavior.

## Why it is not a duplicate

- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) tracks the
  complete configuration execution lifecycle. This ticket owns the narrower
  Antigravity legacy-path detection, precedence, and migration contract that
  lifecycle must call before publication.

## What probably needs to be done

1. Verify which supported Antigravity versions still read the legacy path.
2. Inspect both locations without exposing MCP headers or other credentials.
3. Define deterministic states for legacy-only, canonical-only, equivalent
   dual files, and conflicting dual files.
4. Show a non-blocking migration notice during preview and require an explicit
   migration decision when the files conflict.
5. Gate Antigravity MCP Apply on the completed migration contract.

## Acceptance criteria

- Tier 1 tests cover legacy-only, canonical-only, equivalent, and conflicting
  dual-file states.
- Preview reports legacy presence without exposing configuration values.
- Apply cannot silently create a second active definition when legacy state is
  unresolved.
- Migration preserves unrelated servers and unknown fields.
- Live verification records behavior on every supported Antigravity major line.

## Sources

- `internal/mcpconfiguration/inspection.go:48-95`
- `internal/hostlayout/layout.go:55-63`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`
- [Antigravity MCP documentation](https://antigravity.google/docs/mcp)
- [Antigravity Gemini CLI migration](https://antigravity.google/docs/gcli-migration)
