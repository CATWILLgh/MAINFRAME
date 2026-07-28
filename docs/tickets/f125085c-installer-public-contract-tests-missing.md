---
id: f125085c
title: install.sh has no public-contract regression test harness
status: open
priority: medium
component: testing
discovered: 2026-07-15
discovered-from: []
tags: ["testing", "installer", "rollback", "filesystem", "regression"]
---

# f125085c: install.sh has no public-contract regression test harness

## What was observed

The installer mutates global files, symlinks, shell startup files, permissions, backups, and tool-specific configuration. The repository now has two partial isolated suites: `tools/test_install.py` covers dry-run preflight and adapter failures, while `tools/test_install_migration_cleanup.py` executes the real install/reinstall/uninstall lifecycle for legacy-symlink cleanup inside a temporary home. The complete managed-target contract is still not covered.

`tools/test_build_opencode_config.py` explicitly expects the single rolling backup to contain the immediately previous generated state after a second write, thereby locking in loss of the original pre-hub state rather than testing recoverability.

## Why it is a problem

The highest-blast-radius component is verified mainly by manual runs. Ownership, idempotency, interruption, dry-run fidelity, and rollback regressions can reach the user's global environment before being noticed.

## Why it is not a duplicate

- [#6d09e7be](6d09e7be-install-sh-silent-success-on-missing-source.md) requests one regression case for missing sources; it does not establish a general installer harness.
- [#140f9466](140f9466-config-delivery-non-atomic-rollback-loss.md) owns transactional behavior; this ticket owns the reusable test boundary.

## What probably needs to be done

- Run the installer in a temporary `HOME` with stubbed tool discovery and fixture outputs.
- Test install, repeat install, dry-run, uninstall, foreign-file preservation, failed generation, interrupted publication, and restoration.
- Assert observable filesystem and exit-code contracts, not internal shell function calls.

## Acceptance criteria

- A Tier 1 installer test suite runs without touching the real home directory or network.
- Every managed global target has install, idempotency, foreign-owner, and uninstall coverage.
- Known tickets for source absence, instruction preservation, secret sourcing, and rollback each have a reproducing regression test before their fix.

## Sources

- `install.sh:1-1117`
- `tools/test_build_opencode_config.py:99-109`
- No `tools/test*install*` file exists as of 2026-07-15.

## Re-occurrence noted (2026-07-15)

**Noticed during:** Follow-up review after installer fail-closed repair (`#6d09e7be`)
**Where:** `tools/test_install.py`
**Additional details:** The new suite establishes an isolated dry-run boundary and covers required-source and adapter-failure contracts, but it still forces `--dry-run` for every scenario. It therefore does not yet observe installation, repeated installation, foreign-owner preservation, or uninstall mutations. Full approval also depends on reproducing the separate secret migration (`#208a31bf`), OpenCode instruction preservation (`#c343fe75`), and rollback (`#140f9466`) contracts before their fixes.

## Re-occurrence noted (2026-07-15, migration cleanup)

**Noticed during:** Ownership repair for post-migration symlink cleanup (`#b39e1c99`)
**Where:** `tools/test_install_migration_cleanup.py`
**Additional details:** A second Tier 1 suite now performs real install, repeat-install, dry-run, backup-failure, and uninstall checks in a copied repository and temporary home. This closes those contracts for the legacy-cleanup slice only; current targets, secret sourcing, adapter configuration, interruption, and full rollback remain open under this ticket.
