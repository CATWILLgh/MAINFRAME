---
id: 140f9466
title: Legacy OpenCode configuration publication has incomplete transaction guarantees
status: open
priority: medium
component: delivery
discovered: 2026-07-15
discovered-from: []
tags: ["delivery", "atomicity", "rollback", "configuration", "installer"]
---

# 140f9466: Legacy OpenCode configuration publication has incomplete transaction guarantees

## What was observed

The compatibility OpenCode writer copies configuration to a single rolling
backup and then replaces the live file. Repeated runs can overwrite the last
pre-hub snapshot.

The OpenCode writer performs the backup and live rewrite even when the generated configuration is byte-for-byte unchanged. Routine reinstallations therefore churn file metadata and replace the only rollback snapshot without any effective configuration change.

Permission ownership and preservation are tracked in [#4b83441a](4b83441a-opencode-missing-rules-allow-all.md); this ticket is limited to publication and rollback mechanics.

## Why it is a problem

A concurrent writer, path race, metadata mismatch, or later bad run can make
the rolling backup insufficient to restore the original user configuration.

## Why it is not a duplicate

- [#c343fe75](c343fe75-opencode-agents-md-clobbers-user-file.md) covers ownership of the OpenCode instructions target.
- [#c71185b2](c71185b2-opencode-json-plaintext-api-keys.md) covers secret storage in configuration and backup files, not transactionality.
- [#06cb98c8](06cb98c8-publish-opencode-config-and-ownership-consistently.md) covers consistent publication of configuration and its ownership registry.
- [#66ab4af8](66ab4af8-make-bundle-publication-atomic.md) covers generated bundle directories, not the legacy user-configuration writer.
- [#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) covers the new common executor and recovery boundary.

## What probably needs to be done

- Retire the compatibility writer in favor of the common executor or give it
  the same descriptor-relative traversal, locking, and recovery guarantees.
- Define a durable original-state and metadata-preservation policy.
- Skip publication and backup rotation when the validated desired bytes equal the live file.

## Acceptance criteria

- A concurrent or interrupted publication cannot overwrite an unobserved replacement.
- Symlinks and path-component swaps fail closed.
- Repeated installations preserve a restorable original user state without accumulating plaintext-secret snapshots.
- An unchanged OpenCode render performs no live rewrite and does not rotate the rollback copy.

## Sources

- `adapters/opencode/config_writer.py`
- [#06cb98c8](06cb98c8-publish-opencode-config-and-ownership-consistently.md)
- [#66ab4af8](66ab4af8-make-bundle-publication-atomic.md)
- [#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md)

## Historical note (2026-07-15, superseded)

**Noticed during:** Repair and independent edge review of Codex permission decisions (`#95878fc4`)
**Where:** `adapters/codex/build_codex.py`, generated-output publication order
**Additional details:** Native rule validation completed before all writes, but
a later output failure could still expose a mixed generated tree. Generated
bundle publication was subsequently resolved by
[#66ab4af8](66ab4af8-make-bundle-publication-atomic.md).

## Historical note (2026-07-15, superseded)

**Noticed during:** Fail-closed permission-source repair (`#4b83441a`)
**Where:** `adapters/opencode/build_opencode.py`, configuration and permission-ownership state publication
**Additional details:** The generator wrote `opencode.json` before its ownership
sidecar. The remaining cross-file ownership transition is now owned by
[#06cb98c8](06cb98c8-publish-opencode-config-and-ownership-consistently.md).

## Re-occurrence noted (2026-07-15, secure OpenCode writer)

**Noticed during:** Fresh-config mode repair (`#3da176c4`)
**Where:** `adapters/opencode/config_writer.py`, backup/live publication and parent creation
**Additional details:** Deterministic fault probes found three remaining
transaction boundaries. A concurrent writer can replace the live inode after
the final identity check and still be overwritten by the following
`os.replace`; a run that detects a changed live inode after publishing the
recovery backup has already rotated away the older backup; and parent creation
can follow or race into a symbolic link because it is path-based rather than a
descriptor walk. Atomic replacement can also discard hardlink, ACL, and
extended-attribute metadata. Concurrency control, secure descriptor-relative
path traversal, metadata policy, unchanged-write suppression, and rolling
backup recovery remain owned by this ticket.
