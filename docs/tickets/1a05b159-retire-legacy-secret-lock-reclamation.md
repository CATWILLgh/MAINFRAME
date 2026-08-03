---
id: 1a05b159
title: Retire racy stale-lock reclamation in the legacy secret helper
status: closed
priority: medium
component: installer
discovered: 2026-07-29
discovered-from: ["#1c0434d3"]
tags: ["credentials", "concurrency", "legacy", "installer"]
resolved: 2026-08-03
---

# 1a05b159: Retire racy stale-lock reclamation in the legacy secret helper

## What was observed

The compatibility `install.sh` path must remain autonomous until ADR 0087
parity, so it still installs the Bash `secret` helper. Its `mkdir` lock removes
a directory whose recorded process is dead and retries acquisition. Two
waiting processes can both participate in reclamation and race to continue.
Immutable releases no longer use this path: their `secret` wrapper dispatches
to the native MAINFRAME store with an advisory file lock and opaque
generations.

## Why it is a problem

Concurrent legacy-helper mutations can lose an update. Removing stale-lock
reclamation without a replacement would instead leave the helper permanently
blocked after an unclean process exit.

## Why it is not a duplicate

- [#1c0434d3](1c0434d3-stop-retaining-retired-secret-values.md) covers retired
  plaintext in backups. Both legacy and native paths now sanitize successful
  replacement and deletion; this ticket covers legacy lock recovery only.
- ADR 0087 covers complete replacement of `install.sh`; this ticket records the
  specific safety condition that parity must remove or solve.

## What probably needs to be done

- Prefer retiring the compatibility helper when the release installer reaches
  proven parity.
- If the helper must live longer, replace stale-directory deletion with a
  portable single-owner protocol that has an explicit recovery operation.
- Add a deterministic two-writer stale-lock test rather than relying only on
  the normal concurrent-create test.

## Acceptance criteria

- Two legacy-helper writers cannot both pass stale-lock recovery.
- A crashed writer has a documented and tested recovery path.
- No secret value is written to lock metadata or diagnostics.
- Normal concurrent create, replacement, and deletion tests remain green.

## Sources

- `core/resources/credential-tools/secret`
- `tools/test_secret_stdin.py`
- `tools/test_secret_lock.py`
- `docs/decisions/0087-terminal-install-manager.md`
- `internal/secretstore/filesystem.go`
- [POSIX file-system operation atomicity](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap04.html)
- [POSIX `rename()`](https://pubs.opengroup.org/onlinepubs/9799919799/functions/rename.html)
- [POSIX `kill()`](https://pubs.opengroup.org/onlinepubs/009604499/functions/kill.html)

## Resolution

Normal writers no longer reclaim a lock from process metadata. They retain the
portable atomic `mkdir` acquisition, publish only PID and host metadata, and
fail after the existing bounded wait when a lock remains.

Crash recovery is now the explicit `secret recover-lock --confirm` operation.
It creates a recovery barrier that writers check around acquisition, rejects a
live local owner and any foreign-host owner, and moves the stale lock to a
same-filesystem quarantine before deleting it. Missing or malformed owner
metadata requires the stronger `--confirm-unknown` acknowledgement after the
operator verifies that no helper is running. An interrupted recovery fails
closed; help text documents removal of only the recovery barrier after the
operator verifies that recovery itself stopped.

Tier-1 tests deterministically cover two writers facing a stale lock, dead and
live owners, foreign-host refusal, concurrent recovery, unknown metadata,
recovery-barrier contention, and absence of secret values from lock metadata
and diagnostics. Signal handlers now terminate before their exit cleanup, so an
interrupted writer cannot continue after releasing its lock. The existing
create, replacement, deletion, symlink-safety, render, installer, and
immutable-release tests remain green.
