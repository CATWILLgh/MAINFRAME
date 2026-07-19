---
id: 2ac245c4
title: Make global validator hooks independent of the tool working directory
status: open
priority: low
component: hooks
discovered: 2026-07-16
discovered-from: []
tags: ["hooks", "paths", "validation"]
---

# 2ac245c4: Make global validator hooks independent of the tool working directory

## What was observed

After each `apply_patch` operation in the installer worktree, the global
validation hook invokes Python with `/tools/validate-claude-md.py` and
`/tools/smoke-hooklib.py`. Both commands fail because the paths are resolved
from `/` instead of the MAINFRAME checkout. The requested patch still applies.

## Why it is a problem

The hook emits a false failure after every edit and does not run the validation
it claims to enforce. Repeated false failures can hide a real validation error.

## Why it is not a duplicate

No existing ticket describes validator scripts being resolved against the
tool's working directory.

## What probably needs to be done

- Locate the hook command that builds both script paths.
- Resolve shipped validators from the installed MAINFRAME root rather than the
  caller's current working directory.
- Exercise the hook from `/`, the repository root, and a linked worktree.

## Acceptance criteria

- Both validators run from an arbitrary working directory.
- A missing installed validator produces one actionable error containing the
  resolved path.
- Hook tests cover the repository and linked-worktree cases.

## Sources

- `tools/validate-claude-md.py`
- `tools/smoke-hooklib.py`
- Failure observed after `apply_patch` on 2026-07-16

## Re-occurrence noted (2026-07-19)

**Noticed during:** Release-independent installer recovery implementation
**Where:** Every `apply_patch` call from the MAINFRAME repository
**Additional details:** Both validator paths again resolved under `/tools` and
reported a failed tool call after successfully applying each patch. Separate
focused and full verification remained necessary.
