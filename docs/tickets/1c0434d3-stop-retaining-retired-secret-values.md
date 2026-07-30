---
id: 1c0434d3
title: Stop retaining retired secret values in the helper backup
status: closed
priority: medium
component: credentials
discovered: 2026-07-29
discovered-from: ["#2e7c03de"]
tags: ["credentials", "security", "backup", "deletion"]
---

# 1c0434d3: Stop retaining retired secret values in the helper backup

## What was observed

`secret del NAME` and replacement operations call `write_store_atomically`,
which copies the complete pre-mutation `secrets.env` to `secrets.env.bak`
before publishing the new file. A deleted or rotated value therefore
disappears from the primary store but remains readable from the backup until a
later successful mutation replaces that backup.

## Why it is a problem

The command name and help text present deletion as removal, but the retired
secret remains in a known plaintext credential file. This makes cleanup
incomplete and extends the useful lifetime of a revoked value. It also means
an agent cannot truthfully report that `secret del` removed the local stored
value.

## Why it is not a duplicate

- [#2e7c03de](2e7c03de-complete-central-credential-catalog-rollout.md) covers
  catalog records, references, and adapter consumption. This ticket covers the
  value store's backup and retirement semantics.
- [#c71185b2](c71185b2-opencode-json-plaintext-api-keys.md) covers secret values
  copied into OpenCode configuration and its backups. This ticket covers the
  central `secret` helper's own backup.

## What probably needs to be done

- Define whether rollback is allowed to retain a value after explicit deletion
  or rotation; default to the user's retirement intent rather than silent
  plaintext retention.
- Redesign mutation recovery so the post-mutation primary and backup do not
  contain the retired value while an interrupted write remains recoverable.
- Cover `set`, `create-stdin`, `del`, and `edit` separately because their
  overwrite and recovery contracts differ.
- Update helper documentation so deletion and backup behavior are stated
  precisely.

## Acceptance criteria

- After successful deletion, neither the primary store nor the helper-managed
  backup contains the deleted name or value.
- After successful replacement, neither helper-managed file contains the
  previous value.
- Injected interruption tests prove that the store remains syntactically valid
  and recovers to an explicitly documented pre- or post-operation state.
- Files remain regular, no-follow, private, and are published atomically on the
  same filesystem.
- Tests use synthetic canaries and never print a secret value.

## Sources

- `core/resources/credential-tools/secret:16-18`
- `core/resources/credential-tools/secret:108-132`
- `core/resources/credential-tools/secret:288-316`
- `dist/codex/skills/secrets-handling/SKILL.md`
- `docs/tickets/2e7c03de-complete-central-credential-catalog-rollout.md`

## Resolution

Resolved on 2026-07-29.

- Commit `d1a448f` publishes post-change content to both managed files after
  every successful legacy-helper mutation, so replacement and deletion retain
  neither the old name nor the old value.
- Immutable releases route `secret` through the native MAINFRAME store. It
  publishes a new opaque generation before the sanitized backup and primary,
  synchronizes files and the containing directory, and rejects a prepared
  deletion after any intervening mutation or publication failure.
- Historical `0400` stores remain readable without creating lock, backup, or
  generation sidecars. The first native mutation narrows a real legacy
  credentials directory to `0700`.
- Failure injection, maximum-size quoted values, historical assignment forms,
  editor overflow, release assembly, and legacy-helper behavior have regression
  coverage. Independent final review returned `proceed` with no grounded
  blocker.
- Provider-side revocation and values inherited by already running processes
  remain external to local storage retirement.
