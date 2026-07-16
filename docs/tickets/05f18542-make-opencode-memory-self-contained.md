---
id: 05f18542
title: Make the OpenCode memory adapter own its runtime dependencies
status: open
priority: high
component: opencode-memory
discovered: 2026-07-15
discovered-from: []
tags: ["opencode", "memory", "installation", "ownership", "worktrees"]
---

# 05f18542: Make the OpenCode memory adapter own its runtime dependencies

## What was observed

The OpenCode memory plugin is linked from `adapters/opencode/plugins`, but it
executes `store.py` and `memory-reminder.py` through hard-coded paths under
`~/.claude/skills/mainframe/`. A normal baseline MAINFRAME installation always
updates Claude delivery links even when `--opencode` is absent.

Therefore, installing the OpenCode adapter from one worktree and later running a
baseline install from another worktree can leave the OpenCode plugin and its
helpers on different commits. If the second tree lacks those helper files,
OpenCode memory silently fails open.

## Progress — 2026-07-16

The isolated `bundle-v2` delivery now packages the plugin, `store.py`, and
`memory-reminder.py` together. The plugin resolves both helpers relative to its
own module and stores data below `XDG_DATA_HOME`; the legacy installer also
links those OpenCode-owned artifacts without using Claude Code's backup tree.

The ticket remains open because the full lifecycle contract still needs a
second-worktree reinstall test, explicit plugin/helper compatibility
versioning, and a partial-uninstall scenario. The current test covers migration
from a legacy helper link, foreign-file preservation, memory-data preservation,
complete adapter uninstall, and absence of `~/.claude`.

## Why it is a problem

The OpenCode adapter does not own the dependencies required for recall or
reminders. Its behavior changes when an unrelated Claude Code installation is
repointed, violating the repository rule that one component owns its data and
making worktree-based development especially fragile.

## Why it is not a duplicate

- [#a6e1135a](a6e1135a-split-monolithic-installer.md) concerns the size and
  structure of `install.sh`; it does not cover cross-runtime dependency ownership.
- Antigravity is already self-contained, so its plugin lifecycle tickets do not
  address OpenCode's hard-coded Claude path.

## What probably needs to be done

1. Package the memory helper and reminder under an OpenCode-owned installation
   path or make the plugin bundle self-contained.
2. Derive paths from the installed OpenCode component rather than `~/.claude`.
3. Version the helper/plugin contract and fail visibly on incompatibility.
4. Define upgrade, worktree switch, and uninstall ownership explicitly.
5. Remove the implicit requirement that Claude Code delivery remains installed.

## Acceptance criteria

- OpenCode recall and reminders work when `~/.claude/skills/mainframe` is absent.
- Installing baseline MAINFRAME from another worktree cannot change the active
  OpenCode helper version.
- Lifecycle tests cover install, reinstall from another root, partial uninstall,
  foreign files, and preserved memory data.
- Plugin and helper versions are tested as one compatible unit.
- Documentation names the OpenCode-owned runtime paths.

## Sources

- `adapters/opencode/plugins/mainframe-memory.js:4-8`
- `install.sh:694-747`
- `install.sh:1168-1235`
- <https://opencode.ai/docs/plugins>
