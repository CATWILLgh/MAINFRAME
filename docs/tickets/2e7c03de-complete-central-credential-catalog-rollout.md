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

The central contract, TUI, and machine CLI now load, review, create, edit, and
persist the neutral user-instance document without reading secret values. The
current installer still seeds adapter-local Markdown indexes, and the
remaining migration must preserve any divergent user content before those
legacy indexes can be retired.

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

- Inventory every legacy adapter-local index and design a previewed merge that
  preserves divergent user content without deleting the originals.
- Teach shipped agent guidance to consume the merged catalog through that
  interface rather than reading an adapter-local file.
- Complete adapter-specific consumption without reintroducing cross-adapter
  ownership or direct reads of the secret store.

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

## Progress

- `mainframe credentials` now provides a read-only, versioned JSON view.
- `mainframe credentials uses NAME` reports every credential-instance role
  that shares one validated reference without reading the value.
- The neutral user document path is
  `credentials-config/mainframe/instances.json`.
- Missing user state succeeds with an empty list. Present state is read through
  the no-follow bounded host reader and strictly validated.
- The response explicitly reports secret availability as unchecked. It never
  resolves values, reads the secret store, or falls back to adapter-local
  indexes.
- The TUI creates and edits instance metadata through the common reviewed
  transaction and offers known references as reusable choices.
- New secret input is masked and pasteable. A separate value-free confirmation
  calls a create-only stdin helper operation, so existing shared values cannot
  be rotated accidentally.
- Agent-facing create and edit use the versioned `credentials instance
  review` and `credentials instance apply --confirm` protocol over the common
  application transaction. The confirmation binds release, physical target,
  transaction state, exact file before-image, and normalized desired state.
  Secret input remains human-only.
- `mainframe credentials legacy-indexes` and the TUI now assess read-only
  transfer readiness for every old adapter-local index. Missing and
  byte-identical current templates need no transfer, safe divergent files
  require manual transfer, and unsafe files block readiness.
- Readiness inspection never returns content or content hashes and never
  writes, deletes, or adopts an old file. It always reports migration as not
  performed. Actual transfer and retirement of divergent legacy descriptions
  remain open work under this ticket.

## Sources

- `docs/installer-strategy.md`
- `internal/credentialcatalog/`
- `core/resources/credentials-index.md`
- `core/resources/credential-tools/secret`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`
