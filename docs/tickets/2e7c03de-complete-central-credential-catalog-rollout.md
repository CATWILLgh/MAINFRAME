---
id: 2e7c03de
title: Complete the central credential catalog rollout
status: open
priority: medium
component: installer
discovered: 2026-07-27
discovered-from: []
tags: ["credentials", "tui", "migration", "security"]
---

# 2e7c03de: Complete the central credential catalog rollout

## What was observed

The central contract in `docs/installer-strategy.md` and
`internal/credentialcatalog` establish strict read-only service definitions
and user-instance parsing. The current installer still seeds adapter-local
Markdown indexes, and neither the CLI nor TUI can load, merge, edit, or persist
the new user instance document. Live secret resolution and adapter injection
are also intentionally absent.

## Why it is a problem

The foundation alone does not give users or agents one working credential
directory. Enabling writes before migration, ownership, permissions, and
rollback are defined could discard divergent user descriptions or expose
secret values.

## Why it is not a duplicate

- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) covers
  adapter configuration ownership. This ticket covers neutral credential
  metadata and secret-reference lifecycle.

## What probably needs to be done

- Define the neutral user-instance path, file modes, ownership, atomic writes,
  journal behavior, and recovery.
- Inventory every legacy adapter-local index and design a previewed merge that
  preserves divergent user content without deleting the originals.
- Add a read-only `mainframe credentials` interface before enabling edits.
- Teach shipped agent guidance to consume the merged catalog through that
  interface rather than reading an adapter-local file.
- Add TUI instance selection and editing only after read-only behavior is
  verified.
- Resolve values only at the final application boundary and prove that values
  cannot enter arguments, previews, logs, errors, or journals.

## Acceptance criteria

- One neutral user-instance document is authoritative for every adapter.
- Migration previews all legacy inputs and never discards divergent content.
- Unknown schema versions fail without rewriting user data.
- CLI, TUI, and agent guidance distinguish structural catalog validation from
  live secret availability.
- Secret values remain absent from project files, process arguments, previews,
  logs, errors, and executor journals.
- Installation, update, adapter deselection, uninstall, interruption, and
  recovery tests preserve user-owned credential metadata.

## Sources

- `docs/installer-strategy.md`
- `internal/credentialcatalog/`
- `core/resources/credentials-index.md`
- `core/resources/credential-tools/secret`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`
