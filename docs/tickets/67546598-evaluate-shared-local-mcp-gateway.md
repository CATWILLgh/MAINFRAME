---
id: 67546598
title: Evaluate a shared local MCP gateway for stdio servers
status: open
priority: low
component: installer
discovered: 2026-07-17
discovered-from: []
tags: ["tui", "mcp", "stdio", "streamable-http", "process-lifecycle"]
---

# 67546598: Evaluate a shared local MCP gateway for stdio servers

## What was observed

Each adapter process normally starts its own configured stdio MCP child. Four
simultaneous agent windows can therefore create four copies of the same local
server. Existing bridges can expose a stdio command through Streamable HTTP,
which could let all adapters target one loopback endpoint instead.

Transport conversion alone does not prove process sharing. Some proxies keep
one stdio child per HTTP client or MCP session, so a candidate must demonstrate
actual multiplexing into one compatible backend process rather than only a
different client-facing transport.

## Why it is a problem

Duplicate servers consume memory, repeat startup work, and can contend for
local caches or external rate limits. A shared gateway could reduce that cost,
but it also introduces a long-running service, concurrent-client semantics,
port ownership, crash recovery, and a new local security boundary. Binding an
unauthenticated MCP endpoint beyond loopback would expose tool execution to
other hosts and is not acceptable.

## Why it is not a duplicate

- [#8b9e48c4](8b9e48c4-model-external-tooling-lifecycle.md) covers discovery
  and installation policy for optional external executables.
- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) covers
  ownership-aware adapter configuration.

This ticket covers the runtime and concurrency contract for sharing one local
MCP backend across multiple adapter clients.

## What probably needs to be done

- Compare maintained stdio-to-Streamable-HTTP bridges with a small owned
  gateway; verify licenses, release cadence, protocol support, and failure
  behavior.
- Prove whether each candidate uses one backend process for multiple clients or
  starts one child per connection or session.
- Define compatibility rules for stateful servers, client roots, sampling,
  elicitation, cancellation, progress notifications, and concurrent calls.
- Define lifecycle ownership: installation, loopback address, port allocation,
  startup, health checks, restart, update, shutdown, logs, and uninstall.
- Require loopback-only binding by default and a per-installation client secret
  if supported adapters can provide an HTTP header without exposing it.
- Preserve direct stdio as a fallback when a server cannot safely share state.

## Acceptance criteria

- A four-client integration test proves the selected design runs exactly one
  backend process while serving all clients correctly.
- Disconnecting or crashing one client does not terminate sessions owned by
  other clients.
- The gateway never binds to a non-loopback interface by default and does not
  expose credentials in adapter configuration previews, logs, or journals.
- Stateful and non-shareable servers are detected or explicitly classified and
  continue to use direct stdio.
- Install, update, restart, recovery, and uninstall behavior is deterministic
  on supported macOS and Linux environments.
- The TUI explains the resource-saving benefit and the additional local
  service before enabling the gateway.

## Sources

- <https://modelcontextprotocol.io/specification/latest/basic/transports>
- <https://github.com/sparfenyuk/mcp-proxy>
- <https://github.com/punkpeye/mcp-proxy>
- <https://github.com/supercorp-ai/supergateway>
- `docs/tickets/8b9e48c4-model-external-tooling-lifecycle.md`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`
