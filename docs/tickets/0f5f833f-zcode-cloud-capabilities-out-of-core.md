---
id: 0f5f833f
title: Keep ZCode cloud and remote capabilities outside the local adapter core
status: open
priority: low
component: zcode-desktop
discovered: 2026-08-05
discovered-from: []
tags: ["zcode", "cloud", "mcp", "remote"]
---

# 0f5f833f: Keep ZCode cloud and remote capabilities outside the local adapter core

## What was observed
ZCode exposes MCP servers, automations, remote development, remote control, bot channels, and cloud workspace features. The requested MAINFRAME scope is local ZCode Desktop and its bundled CLI, without cloud runs or hidden cloud dependencies. Configured MCP servers also auto-connect, which is an activation and authority boundary rather than a passive file projection.

## Why it is a problem
Adding these capabilities to the base adapter would expand network authority and make a local installation depend on services that the user explicitly excluded.

## Why it is not a duplicate
Existing MCP tickets concern Codex or OpenCode configuration formats. This ticket records the ZCode-specific product boundary, not a missing codec defect.

## What probably needs to be done
Leave all cloud and remote features unselected. If the user later requests one, design it as a separate optional feature with a value-free preview, explicit activation approval, independent removal, and no effect on local core readiness.

## Acceptance criteria
- The default ZCode component performs no MCP or remote-service configuration.
- Release tests prove that selecting ZCode alone creates no network-dependent feature intent.
- Any future optional unit has independent preview, apply, rollback, and uninstall tests.
- Documentation distinguishes local model-provider traffic from MAINFRAME-added cloud dependencies.

## Sources
- `adapters/zcode-desktop/capabilities.json`
- https://zcode.z.ai/en/docs/mcp
- https://zcode.z.ai/en/docs/automations
