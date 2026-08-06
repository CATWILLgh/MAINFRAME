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

## Re-occurrence noted (2026-08-06) — the release bundle carries the whole file

**Noticed during:** modelling per-rule ownership of the three permission lists
**Where:** `adapters/claude-code/build_bundle.py:252,277` — `copy_regular_file(dist/claude-code/settings.json, output/settings.json)`

The dual-ownership problem has a sharper consequence than this ticket records:
because the same file is both the render target and the live user configuration,
**every Claude Code release bundle embeds the maintainer's personal settings**. A
bundle built here contains `model`, `effortLevel`, `advisorModel`, `language`,
`editorMode`, `verbose`, `teammateMode`, `remoteControlAtStartup`,
`enabledPlugins`, `autoMemoryEnabled`, `autoCompactEnabled`,
`preferredNotifChannel`, `cleanupPeriodDays`, `skipWorkflowUsageWarning` and the
`env` map — verified by building the bundle and listing the payload's keys.

Today the blast radius is local: releases are built and installed on the same
machine. It becomes a disclosure the moment a bundle is shared, and `env` is
exactly the shape that holds a token in some setups. Priority left unchanged
because nothing is published yet; raise it before any release leaves this
machine.

**Fix direction, and it converges with the per-rule ownership work:** the bundle
does not need the whole file. Once the resource declares claims over
`/permissions/allow`, `/permissions/ask` and `/permissions/deny`, the only source
content a release needs is those three lists. Ship a policy-only document as the
resource source instead of copying the live file, and the leak closes as a side
effect of the ownership change rather than as separate work.
