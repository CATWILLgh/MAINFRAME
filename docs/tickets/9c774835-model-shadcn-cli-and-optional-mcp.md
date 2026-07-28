---
id: 9c774835
title: Model shadcn CLI and optional MCP as a developer tool
status: open
priority: low
component: installer
discovered: 2026-07-28
discovered-from: ["#8b9e48c4", "#67546598"]
tags: ["shadcn", "cli", "mcp", "developer-tools"]
---

# 9c774835: Model shadcn CLI and optional MCP as a developer tool

## What was observed

MAINFRAME already ships a shadcn skill whose primary workflow invokes the
project package runner and the shadcn CLI on demand. Official shadcn
documentation describes its local MCP server as a bridge between an agent,
component registries, and the same CLI. The MCP process is started with
`shadcn@latest mcp`; it is not a remote credential-backed service and is not
required for normal CLI use.

## Why it is a problem

Treating shadcn as only an MCP server would hide its CLI dependency and create
one local standard-input/output process per client session. Treating it as a
credential service would mix unrelated concepts. MAINFRAME does not yet
project shadcn onto its planned external-tool prerequisite model while keeping
the optional adapter-specific MCP layer separate.

## Why it is not a duplicate

- [#2e7c03de](2e7c03de-complete-central-credential-catalog-rollout.md) covers
  migration of user credential metadata. shadcn does not require a credential
  in its default public-registry workflow.
- [#8b9e48c4](8b9e48c4-model-external-tooling-lifecycle.md) owns the general
  model for external executables and package-manager prerequisites. This
  ticket defines only the shadcn-specific projection onto that model.
- [#67546598](67546598-evaluate-shared-local-mcp-gateway.md) owns shared local
  MCP process lifecycle. This ticket only decides when shadcn uses direct CLI
  or requests an optional adapter MCP configuration.

## What probably needs to be done

- Represent shadcn CLI-on-demand on top of the typed prerequisite capabilities
  from #8b9e48c4, with Node.js and a project package runner as prerequisites.
- Offer the local shadcn MCP server only as an optional adapter-specific mode.
- Defer process sharing to #67546598 rather than defining another gateway here.
- Verify the current CLI and MCP commands against official documentation
  before implementation.

## Acceptance criteria

- MAINFRAME can describe shadcn through the external-tool lifecycle without
  installing it globally or creating a competing tool catalog.
- The terminal interface explains that CLI use is sufficient and MCP is
  optional.
- Selecting CLI-only mode does not write MCP configuration.
- Selecting MCP mode declares and validates its CLI and Node.js prerequisites.
- Claude Code, Codex, OpenCode, and Antigravity receive only their own selected
  configuration.
- Lifecycle tests cover enable, no-op, disable, reinstall, missing package
  runner, and multiple simultaneous client sessions.

## Sources

- `core/skills/shadcn/SKILL.md:14`
- `core/skills/shadcn/SKILL.md:154`
- `docs/tickets/8b9e48c4-model-external-tooling-lifecycle.md`
- `docs/tickets/67546598-evaluate-shared-local-mcp-gateway.md`
- https://ui.shadcn.com/docs/cli
- https://ui.shadcn.com/docs/mcp
- https://ui.shadcn.com/docs/changelog/2025-08-cli-3-mcp
