---
id: 2409d7e0
title: Claude settings file mixes generated policy with live user-owned configuration
status: open
priority: medium
component: claude-code-configuration
discovered: 2026-07-15
discovered-from: []
tags: ["architecture", "claude-code", "settings", "ownership", "render"]
---

# 2409d7e0: Claude settings file mixes generated policy with live user-owned configuration

## What was observed

`dist/claude-code/settings.json` is both a committed render target and the live user-editable source for every field outside `permissions.allow`, `permissions.deny`, and `permissions.ask`. The installer symlinks this repository file directly to `~/.claude/settings.json`, and `render_core.py --check` intentionally ignores non-policy fields.

## Why it is a problem

The file has two owners and two incompatible lifecycle rules. A local application edit dirties the repository, CI cannot distinguish an intentional user setting from accidental generated-tree drift, and checkout or branch changes can mutate live global behavior. The current working tree demonstrates this coupling through a modified `dist/claude-code/settings.json`.

## Why it is not a duplicate

[#140f9466](140f9466-config-delivery-non-atomic-rollback-loss.md) covers publication atomicity. This ticket covers source ownership and the direct repository-to-live symlink for Claude settings.

## What probably needs to be done

- Separate authored hub policy from machine-local Claude settings.
- Publish a composed live settings file or a supported settings fragment without treating user state as committed render output.
- Define ownership, backup, merge, and conflict behavior for every top-level key.

## Acceptance criteria

- Normal Claude settings changes cannot dirty the MAINFRAME repository.
- `dist/` contains only reproducible outputs with authored sources.
- Hub policy updates preserve user-owned settings without a mixed-ownership file.
- Tests cover first install, user edit, hub update, conflict, and uninstall.

## Sources

- `install.sh:140-151`
- `tools/render_core.py:228-265`
- `docs/layers/settings.md:14-16`, `docs/layers/settings.md:77-103`
