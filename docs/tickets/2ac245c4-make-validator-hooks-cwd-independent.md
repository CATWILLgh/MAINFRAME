---
id: 2ac245c4
title: Make project validator hooks independent of the tool working directory
status: open
priority: low
component: hooks
discovered: 2026-07-16
discovered-from: []
tags: ["hooks", "paths", "validation"]
---

# 2ac245c4: Make project validator hooks independent of the tool working directory

## What was observed

After each `apply_patch` operation in the installer worktree, the project-local
`.codex/hooks.json` invoked validators through
`${CLAUDE_PROJECT_DIR}/tools/...`. Codex did not set the Claude-specific
variable, so Python tried `/tools/validate-claude-md.py` and
`/tools/smoke-hooklib.py`. The requested patch still applied.

The broken untracked hook file was removed during repository cleanup on
2026-07-28. Its durable source and supported Codex project-root contract remain
unresolved.

## Why it is a problem

The hook emits a false failure after every edit and does not run the validation
it claims to enforce. Repeated false failures can hide a real validation error.

## Why it is not a duplicate

This ticket supersedes the untracked `63bbc12b`, which recorded the same
project-local failure with more precise provenance.

## What probably needs to be done

- Establish a tracked source for project-local Codex validator hooks.
- Resolve shipped validators from the installed MAINFRAME root rather than the
  caller's current working directory or a Claude-only environment variable.
- Exercise the hook from `/`, the repository root, and a linked worktree.

## Acceptance criteria

- Both validators run from an arbitrary working directory.
- A missing installed validator produces one actionable error containing the
  resolved path.
- Hook tests cover the repository and linked-worktree cases.

## Sources

- `tools/validate-claude-md.py`
- `tools/smoke-hooklib.py`
- Removed local `.codex/hooks.json`, inspected during cleanup on 2026-07-28

## Re-occurrence noted (2026-07-19)

**Noticed during:** Release-independent installer recovery implementation
**Where:** Every `apply_patch` call from the MAINFRAME repository
**Additional details:** Both validator paths again resolved under `/tools` and
reported a failed tool call after successfully applying each patch. Separate
focused and full verification remained necessary.
