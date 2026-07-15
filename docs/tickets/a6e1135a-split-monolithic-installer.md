---
id: a6e1135a
title: Split the monolithic multi-runtime installer
status: open
priority: medium
component: installer
discovered: 2026-07-15
discovered-from: []
tags: ["refactor", "install", "architecture"]
---

# a6e1135a: Split the monolithic multi-runtime installer

## What was observed

`install.sh` is now 1285 lines and owns shared backup behavior, dependency
bootstrap, migration cleanup, and four runtime-specific install/uninstall
paths. The Antigravity addition could keep its own functions short, but every
new target still increases one monolithic entrypoint.

## Why it is a problem

This is a god script: unrelated adapter changes share one shell scope and one
large regression surface. Backup boundaries already differ between Claude,
Codex, and Antigravity, so accidental reuse of the wrong helper can move user
data into an unsafe or runtime-visible location.

## Why it is not a duplicate

No existing ticket covers decomposition of the installer by runtime ownership.

## What probably needs to be done

Keep a small public `install.sh` dispatcher, move shared primitives into one
tested shell library, and move each runtime's preflight/install/uninstall flow
into an owned module. Preserve Bash 3.2 compatibility, the current flags,
failure aggregation, dry-run guarantees, and backup formats.

## Acceptance criteria

- The public installer entrypoint is below the project file-size limit.
- Each runtime adapter owns a bounded install/uninstall module.
- Existing migration, backup, dry-run, failure-aggregation, and idempotency
  tests pass unchanged or with stronger public-contract assertions.
- A failing runtime module cannot skip the remaining requested adapter reports
  or print a false successful completion.

## Sources

- `install.sh`
- `tools/test_install.py`
- `tools/test_install_migration_cleanup.py`
