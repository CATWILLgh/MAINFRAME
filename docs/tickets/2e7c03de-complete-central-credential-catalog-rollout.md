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
current installer still seeds historical credential sources, and the remaining
migration must preserve any divergent user content before those locations can
be retired.

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

- Inventory every historical credential source and design a previewed merge that
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
- Secret values remain absent from project files, catalog responses, previews,
  logs, errors, and executor journals. Authenticated commands receive a value
  only at execution time; agent guidance does not claim the runtime redacts
  subprocess arguments or transcripts.
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
  transfer readiness for every historical credential location. Missing and
  byte-identical current templates need no transfer, safe divergent files
  require manual transfer, and unsafe files block readiness.
- Readiness inspection never returns content or content hashes and never
  writes, deletes, or adopts an old file. It always reports migration as not
  performed. Actual transfer and retirement of divergent legacy descriptions
  remain open work under this ticket.
- Read-only inspection now distinguishes the Claude Code location as the
  historical original shared catalog and the Codex, OpenCode, and Antigravity
  locations as defensive checks for later adapter copies. This is location
  metadata, not a claim that any present file has verified ancestry. Missing
  copies are normal; divergent and unsafe copies retain the same strict
  readiness rules.
- A separate partial reference-discovery preview now extracts exact named
  `secret get NAME` uses from the shared original, using the same bounded
  no-follow snapshot that established eligibility. It preserves repeated uses
  across section paths, distinguishes current catalog-compatible names from
  legacy names, and never returns raw lines or values.
- Excluded examples, malformed or unscoped mentions, and descriptive lines are
  counted. Divergent or blocked adapter copies remain explicit pending sources,
  so discovery cannot be mistaken for migration completion and cannot
  authorize old-file retirement.
- A separate `credentials legacy-plan` command and TUI view now parse every
  safe divergent classified source independently. Proposals retain source and
  section provenance, occurrence counts, unresolved target fields, per-section
  unmapped counts, shared-reference relationships, and possible duplicate
  groups without merging anything.
- The planner pins historical resources to exact components, strategies,
  source paths, target roots, and target paths, and rejects unclassified
  seed-if-absent `.credentials-index` resources. Blocked inputs preserve safe
  source results while blocking overall completion. Catalog enrichment is
  value-free and nonfatal.
- A separate `credentials legacy-review` command now validates partial
  transfer choices against a freshly inspected plan and current catalog. It
  rejects stale proposal identities, invalid targets, contradictory renames,
  and unused proposed instances, then returns a normalized value-free
  after-image.
- A complete set of reference choices with at least one catalog change now
  produces an exact `credentials legacy-apply --confirm` request. Apply
  rechecks the release, catalog, normalized choices, accounting, and every
  classified legacy source by content, mode, device, inode, and birth identity
  before publishing the whole `0600` catalog through one existing application
  transaction.
- Partial descriptive content does not discard recognized references: the
  structured catalog change may be applied while
  `manual_content_review_required` remains true. Blocked sources and pending
  choices still prevent apply. Historical files are never written, deleted, or
  retired, and partial content can never make retirement ready.
- The source recheck during the locked application refresh is the transfer
  linearization point. External editors do not share the transaction lock, so
  a later legacy-file edit remains a new pending migration rather than
  retroactively changing the catalog publication.
- The TUI now edits the same transfer draft in isolated in-memory state. Reuse,
  create, and explicit skip choices do not modify the live credential catalog
  or make its ordinary edit draft dirty. The review reports pending choices,
  manual content review, and accounting readiness without offering apply or
  retirement.
- Shipped guidance now discovers references through `mainframe credentials`
  first on Claude Code, Codex, OpenCode, and Antigravity. It validates the
  catalog schema, requires an exact instance match, and uses an adapter-local
  legacy index only when the CLI is unavailable or a valid catalog has no
  exact match. Catalog errors fail closed without consulting legacy metadata.
- Value consumption remains separate: an independently supplied `$NAME` or
  `$(secret get NAME)` is expanded by the local command environment. Guidance
  now forbids echoing values, shell tracing, and verbose modes that may expose
  credentials instead of promising runtime transcript redaction.
- This is a staged compatibility step, not delivery completion. On the
  inspected machine `secret` is available but `mainframe` is not currently on
  `PATH`, so the documented fallback remains necessary until CLI delivery and
  the reviewed legacy transfer are complete.
- User-confirmed completion of unresolved descriptive content, delivery
  activation, and retirement of old files remain open work under this ticket.

## Sources

- `docs/installer-strategy.md`
- `internal/credentialcatalog/`
- `core/resources/credentials-index.md`
- `core/resources/credential-tools/secret`
- `docs/tickets/cd5f584d-complete-configuration-lifecycle-semantics.md`

## Re-occurrence noted (2026-07-29)

**Noticed during:** Verification that agents have full CRUD access after legacy
catalog transfer.
**Where:** `internal/credentialcatalog/editor.go:134-169` and
`cmd/mainframe/credential_instance_protocol.go:15-16`.
**Additional details:** The reviewed machine protocol supports read, create,
and edit, but has no delete operation; planning explicitly rejects an omitted
existing instance as unsupported deletion. Editing also preserves the existing
`service_id`, so changing service requires a separately reviewed replacement
workflow. Full agent CRUD therefore remains incomplete and must be designed
without allowing stale confirmation, accidental shared-reference loss, or
secret-value reads.

## Progress (2026-07-29) — reviewed deletion and local retirement

- The versioned instance protocol now supports explicit deletion. Review
  returns a before-image and the complete desired catalog; apply repeats the
  review against fresh state and never cascades into the value store.
- Deletion is blocked when a removed record's secret name remains in a known
  MAINFRAME-managed adapter ownership registry. The check runs during review
  and again inside the common transaction lock before catalog publication.
- Immutable releases install a thin `secret` wrapper over native Go
  persistence. File and directory synchronization, advisory locking, opaque
  generations, and sanitized post-change backups replace the racy Bash lock
  and pre-change plaintext backup on that path. The autonomous `install.sh`
  path retains its Bash helper until installer parity, but successful changes
  now publish sanitized post-change content to both of its managed files.
- Agents can prepare and apply deletion of an unreferenced local value through
  a value-free digest-bound protocol. Catalog uses, all fixed managed
  registries, store generation, release, and physical paths are rechecked.
- Provider-side revocation, already inherited process environments, delivery
  activation, and retirement of historical description files remain outside
  this completed unit. The overall rollout ticket therefore remains open.
