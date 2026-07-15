---
id: 11ea7ba3
title: Prevent stale whole-file writes from losing project memory updates
status: open
priority: medium
component: portable-memory
discovered: 2026-07-15
discovered-from: []
tags: ["memory", "concurrency", "data-integrity", "worktrees"]
---

# 11ea7ba3: Prevent stale whole-file writes from losing project memory updates

## What was observed

`write_memory()` locks only the final replacement. Callers read a complete file,
modify it outside the lock, then submit another complete file without the
revision they observed. In a deterministic experiment, two writers both read
`base`, appended different facts, and wrote sequentially; the final file kept
only the last writer's fact.

The adapter instructions explicitly require complete-file replacement, while
Antigravity supports concurrent sessions and asynchronous subagents sharing the
same Git-common-directory memory identity.

## Why it is a problem

Atomic rename prevents partial bytes but not lost updates. Durable facts can be
silently erased during normal parallel work, undermining the central purpose of
long-term memory. No conflict is reported to the model or user.

## Why it is not a duplicate

- [#e0f591b1](e0f591b1-bound-memory-file-reads.md) covers read resource bounds.
- [#2a665dde](2a665dde-validate-memory-version-on-read.md) covers format
  compatibility, not concurrent modification.
- [#b21de3c2](b21de3c2-serialize-antigravity-advisory-queue.md) concerns transient
  hook notes, not durable memory files.

## What probably needs to be done

1. Return a stable content revision, such as SHA-256, from `load` and `check`.
2. Require or support an expected revision on replacement writes.
3. Reject stale writes with a machine-readable conflict response.
4. Document a reload, merge, deduplicate, check, and retry workflow.
5. Keep atomic rename and size validation for successful writes.

## Acceptance criteria

- Two writers starting from the same revision cannot silently overwrite each
  other; exactly one succeeds and the other receives a conflict.
- A retry test merges both durable facts without duplication.
- Worktrees sharing a Git common directory exercise the same conflict behavior.
- Absent-file creation and independent topic-file writes remain supported.
- The command contract documents revision fields and conflict exit behavior.

## Sources

- `core/memory/store.py:223-242`
- `core/memory/store.py:245-315`
- `core/memory/store.py:377-384`
- `adapters/antigravity-2/instructions/70-memory.md:20-23`
- `adapters/opencode/instructions/70-memory.md:11-18`
- <https://antigravity.google/docs/subagents>
