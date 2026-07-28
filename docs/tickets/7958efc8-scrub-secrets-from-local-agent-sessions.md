---
id: 7958efc8
title: Safely scrub exposed credentials from local agent sessions
status: needs-refinement
priority: medium
component: credentials
discovered: 2026-07-27
discovered-from: []
tags: ["credentials", "sessions", "retention", "redaction", "maintenance"]
---

# 7958efc8: Safely scrub exposed credentials from local agent sessions

## What was observed

Users may intentionally give a credential to an agent so it can configure a
service faster. Even when remote model training is disabled, the credential may
remain in local session transcripts, caches, indexes, backups, or derived
artifacts after the configuration work is complete.

The supported session stores, their formats, and their integrity requirements
have not yet been inventoried. No local session contents were inspected while
creating this ticket.

## Why it is a problem

Long-lived local copies increase the time and number of places in which an
otherwise valid credential can be recovered. Blind search-and-replace is not an
acceptable solution: it could corrupt a session database, invalidate indexes or
checksums, miss encoded copies, or rewrite unrelated high-entropy text.

## Why it is not a duplicate

- [#8f2571e3](8f2571e3-runtime-telemetry-and-session-state-have-no-retention-policy.md)
  limits MAINFRAME telemetry and temporary state; it does not redact third-party
  agent conversations.
- [#d0251020](d0251020-add-safe-secret-input-for-tui.md) prevents secret exposure
  during future terminal input; it does not remove values already stored in
  sessions.
- [#c71185b2](c71185b2-opencode-json-plaintext-api-keys.md) moves OpenCode
  configuration keys into the credential store; it does not cover conversation
  history.

## What probably needs to be done

- Inventory each supported agent's local session formats, derived indexes,
  backups, locking rules, and official retention or deletion mechanisms.
- Define which credential values are eligible without broadly reading the
  credential store or persisting a second plaintext copy.
- Select cleanup scope by one exact catalog secret reference. Show every
  credential-instance role that shares that reference before scanning, so one
  deliberate cleanup can cover several servers or services without guessing
  from a high-entropy value.
- Resolve only the selected reference inside the bounded scan operation. Do not
  enumerate or broadly load the secret store, and never include the resolved
  value in preview, logs, reports, backups, or redaction markers.
- Prefer a vendor-supported deletion or redaction interface where one exists.
- Design a bounded scheduled maintenance job with preview, explicit scope,
  backup or rollback, concurrency protection, and a dry run.
- Replace confirmed occurrences with a stable redaction marker while preserving
  the surrounding session where the format safely permits it.
- Make unsupported, encrypted, signed, malformed, active, or unknown-version
  stores fail closed without modification.
- Define whether complete session deletion is the only safe option for formats
  that cannot be rewritten reliably.

## Acceptance criteria

- Supported environments and exact storage versions are explicitly listed.
- No session is modified while its owning process may be writing to it.
- Preview reports affected sessions and occurrence counts without showing
  credential values or surrounding sensitive text.
- Scheduled execution is opt-in, bounded, idempotent, and recoverable.
- Unknown formats and ambiguous matches remain untouched with a clear result.
- Tests use synthetic credentials and fixtures; verification never reads or
  prints real credential values.
- Post-cleanup indexes, session loading, and vendor integrity checks remain
  valid for every supported format.

## Sources

- User-reported product idea on 2026-07-27.
- `docs/tickets/8f2571e3-runtime-telemetry-and-session-state-have-no-retention-policy.md`
- `docs/tickets/d0251020-add-safe-secret-input-for-tui.md`
- `docs/tickets/c71185b2-opencode-json-plaintext-api-keys.md`

## Context needed

- Which agent environments should be supported first.
- How the user confirms cleanup when one selected reference is shared by
  several catalog instances.
- Safe behavior for active sessions and stores without transactional rewrite.
- Default retention window, schedule, and backup lifetime.
