---
id: 3f750372
title: Prevent core rendering from following symbolic-link targets
status: open
priority: medium
component: renderer
discovered: 2026-07-15
discovered-from: []
tags: ["symlink", "filesystem", "render", "safety"]
---

# 3f750372: Prevent core rendering from following symbolic-link targets

## What was observed

`render_core.py` treats a target file reached through a symbolic link as an ordinary file. During `--write`, `shutil.copy2()` follows that link and overwrites the external target; the subsequent render check can report success while the managed path remains a link.

## Why it is a problem

Generated-output reconciliation must not mutate files outside its owned `dist` tree. Fixing only the final filename is insufficient because a parent directory can also redirect the path.

## Why it is not a duplicate

[#66ab4af8](66ab4af8-make-bundle-publication-atomic.md) covers release bundle staging and publication. This ticket covers the neutral-core renderer and all of its file and directory mappings.

## What probably needs to be done

- Validate every target path component without following symbolic links.
- Replace owned target links safely or fail before any write, based on mapping ownership.
- Make `--check` report linked targets as drift even when their resolved bytes match.
- Cover file links, directory links, dangling links, and parent-segment links.

## Acceptance criteria

- `--write` never changes a file outside the configured render target tree.
- `--check` rejects every linked target or parent segment.
- Existing regular-file and executable-mode reconciliation remains idempotent.
- Regression tests verify external sentinel bytes and modes remain unchanged.

## Sources

- `tools/render_core.py:196`
- `tools/render_core.py:230`
- `tools/test_render_core.py`
- `adapters/claude-code/plugin.json`
