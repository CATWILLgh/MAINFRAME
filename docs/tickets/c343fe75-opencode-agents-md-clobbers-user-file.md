---
id: c343fe75
title: OpenCode installation replaces the user's AGENTS.md without preservation
status: open
priority: high
component: install
discovered: 2026-07-15
discovered-from: []
tags: ["opencode", "installer", "data-loss", "rollback", "ownership"]
---

# c343fe75: OpenCode installation replaces the user's AGENTS.md without preservation

## What was observed

`install_opencode()` runs `ln -sfn` from the generated global instructions to `~/.config/opencode/AGENTS.md`. An existing user file or symlink is replaced without ownership detection, backup, merge, or explicit confirmation. A direct audit probe reproduced the replacement.

## Why it is a problem

Installation can destroy user-authored global instructions outside the repository. Uninstall removes only the hub symlink and cannot restore the displaced content, so the operation is not safely reversible.

## Why it is not a duplicate

- [#5fae0bfa](5fae0bfa-opencode-tuned-agents-md-variant.md) covers the generated instruction dialect, not preservation of an existing target.
- [#c71185b2](c71185b2-opencode-json-plaintext-api-keys.md) covers credential storage, not instruction-file ownership.

## What probably needs to be done

- Detect whether the target is absent, already hub-owned, or user-owned.
- Preserve user-owned content before replacement and record enough ownership metadata for uninstall to restore it.
- Require explicit acknowledgement if safe composition is impossible.

## Acceptance criteria

- Installation never removes an unowned `AGENTS.md` without an explicit, recoverable decision.
- Repeated installation is idempotent for a hub-owned link.
- Uninstall restores preserved user content and does not touch unrelated files.
- Installer contract tests cover regular files, foreign symlinks, hub symlinks, missing targets, and interrupted runs.

## Sources

- `install.sh:634-672`, `install.sh:675-685`
- Direct installation probe, 2026-07-15: an existing user `AGENTS.md` was replaced by the hub symlink.

## Design review note (2026-07-15)

Three independent pre-implementation review rounds rejected the automatic preservation-and-restore state machine. Each round found a new interruption or race window: replacement during publication, ambiguous recovery ownership, and non-resumable metadata cleanup. No production or delivery code was changed.

The user selected the larger transactional restoration design with durable state. A new review cycle starts from a monotonic `cleaning` state whose only permitted work is deleting already-committed metadata, with the state record removed last.

## Transaction design review note (2026-07-15)

The Python transaction core passed the third review without a remaining data-loss objection. The review still returned the implementation because secure directory creation covered only two missing levels and would regress a valid deeply nested `XDG_CONFIG_HOME` that the current installer creates with `mkdir -p`.

The required next revision is concrete: walk from the nearest existing physical ancestor, pin each directory descriptor, create each missing component with descriptor-relative `mkdir`, synchronize its parent, and test nested missing paths plus existing symlink components. The three-round cap stopped implementation before code changes.

## Refined implementation direction (2026-07-15)

The reviewed direction is an OpenCode-specific Python transaction invoked by `install.sh`, not more inline shell state. Its durable manifest records `absent`, `preserving`, `preserved`, `restoring`, and monotonic `cleaning` phases. Original content, proof, and managed-link quarantine stay in a private same-filesystem directory; a post-install user replacement moves to a unique visible conflict sibling instead of being overwritten.

Required invariants established by review:

- exact raw link text is the only proof that the current link belongs to this checkout;
- publication and every move use exact, atomic no-replace operations (`RENAME_EXCL` on macOS, `RENAME_NOREPLACE` on Linux);
- regular files and symbolic-link objects are compared by `lstat` device and inode without following links;
- the target filesystem is capability-probed before the original name is moved;
- state data and affected directories are synchronized before a phase advances;
- install and uninstall are serialized with a process-released file lock;
- `cleaning` never touches the restored target or a conflict copy and deletes the manifest last;
- uninstall does not require the generated source to still exist;
- restoration runs before other OpenCode links are removed, while installation publishes `AGENTS.md` before agents, plugins, and skills;
- malformed state, unsupported file types, destination collisions, or directory-identity drift fail without deleting any surviving object.

Remaining entry-path work:

- securely create every missing component of a nested `XDG_CONFIG_HOME` from the nearest existing physical ancestor with pinned directory descriptors, descriptor-relative `mkdir`, and parent synchronization;
- preserve valid symlinked `XDG_CONFIG_HOME` and symlinked `opencode` directory layouts while rejecting identity changes during the transaction;
- add isolated public lifecycle tests plus deterministic interruption tests after every durable mutation and every partial `cleaning` deletion.

Authoritative basis and experiments already checked:

- POSIX directory operations are individually atomic, while ordinary rename may replace its destination;
- the installed macOS SDK exposes `renameatx_np(..., RENAME_EXCL)` and the installed manual confirms `EEXIST` without replacement;
- the local filesystem successfully hard-links both regular files and broken symbolic-link objects and supports directory `fsync`;
- the copied-repository temporary-`HOME` fixture pattern in `tools/test_install_migration_cleanup.py` can test the lifecycle without touching live delivery.

The broader generator and `opencode.json` transaction boundary remains in [#140f9466](140f9466-config-delivery-non-atomic-rollback-loss.md); this ticket stays limited to `AGENTS.md` ownership and restoration.
