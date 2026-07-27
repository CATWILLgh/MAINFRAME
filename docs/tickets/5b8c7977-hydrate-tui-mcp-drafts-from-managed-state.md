---
id: 5b8c7977
title: Hydrate TUI MCP drafts from managed installation state
status: open
priority: high
component: installer
discovered: 2026-07-27
discovered-from: ["#cd5f584d"]
tags: ["tui", "mcp", "ownership", "lifecycle"]
---

# 5b8c7977: Hydrate TUI MCP drafts from managed installation state

## What was observed

`NewModel` derives selected adapters from observed targets but initializes an
empty `mcpChoices` map. `ensureMCPChoices` then creates choices from catalog
defaults and the current adapter selection, without hydrating which managed
MCP profiles are already installed for which adapters. The combined preview
uses these in-memory choices as desired MCP state.

## Why it is a problem

Opening the TUI for a diagnostics-only or unrelated change can describe an
already managed MCP connection as undesired. Once public Apply is enabled,
that stale draft could prepare removal of working MCP configuration even
though the user did not ask to change MCP.

## Why it is not a duplicate

- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) defines
  ownership-aware configuration planning in general. This ticket covers the
  missing translation from observed managed MCP state into the initial TUI
  draft.
- [#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) covers execution of an
  already correct desired plan, not how the TUI obtains that desired state.

## What probably needs to be done

- Expose a privacy-safe installed MCP selection snapshot from the read-only
  lifecycle inspection.
- Initialize each TUI choice from managed exact state before applying catalog
  defaults.
- Preserve conflicts and relinquished user-owned state without pretending it
  is a clean managed selection.
- Reconcile hydrated choices when adapter selection changes.

## Acceptance criteria

- Opening the TUI and reviewing without changing MCP produces no MCP removal
  for every managed adapter/profile combination.
- Diagnostics-only and adapter-only changes preserve unrelated managed MCP
  state.
- Conflicted, user-modified, and unowned entries remain visible without being
  adopted.
- Tier 1 tests cover fresh install, managed exact state, mixed adapters,
  deselection, conflict, and user-owned matching state.

## Sources

- `internal/tui/model.go:78`
- `internal/tui/mcp_screen.go:85`
- `internal/tui/model.go:164`
- `internal/lifecycle/configuration_preview.go:83`
- `internal/mcpconfiguration/inspection.go`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`
- `docs/tickets/7a1c1d1d-add-safe-plan-application.md`
