---
id: "99382083"
title: Codex installation replaces the whole user hooks file instead of composing it
status: open
priority: medium
component: codex-delivery
discovered: 2026-07-15
discovered-from: []
tags: ["codex", "hooks", "ownership", "composition", "installer"]
---

# 99382083: Codex installation replaces the whole user hooks file instead of composing it

## What was observed

The Codex installer backs up an existing `${CODEX_HOME}/hooks.json` and replaces it with a symlink to `dist/codex/hooks.json`. Unlike item-by-item skills, rules, and agents, hook ownership is all-or-nothing.

## Why it is a problem

Installing MAINFRAME can disable unrelated personal or third-party Codex hooks. Later edits to the user's former file do not participate in the active configuration, and uninstall requires manual reconstruction from timestamped backups.

## Why it is not a duplicate

[#c343fe75](c343fe75-opencode-agents-md-clobbers-user-file.md) covers the analogous OpenCode instruction file. [#140f9466](140f9466-config-delivery-non-atomic-rollback-loss.md) covers atomicity and rollback. This ticket covers Codex hook composition and ownership.

## What probably needs to be done

- Confirm the current Codex hook composition contract from the installed runtime and official documentation.
- Prefer a namespaced or mergeable registration mechanism if supported.
- Otherwise generate a composed file from an explicitly owned fragment while preserving user hooks, with conflict detection and reversible publication.

## Acceptance criteria

- Installing MAINFRAME preserves a pre-existing non-MAINFRAME hook and activates MAINFRAME hooks.
- Reinstall and uninstall are idempotent and do not accumulate or lose user hook entries.
- Conflicts fail clearly before changing the live file.
- Isolated-home tests cover an existing user hook file.

## Sources

- `install.sh:691-696`, `install.sh:801-824`
- `install.sh:838-842`
