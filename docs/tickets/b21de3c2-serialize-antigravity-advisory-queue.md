---
id: b21de3c2
title: Serialize Antigravity advisory queue updates
status: open
priority: medium
component: antigravity-hooks
discovered: 2026-07-15
discovered-from: []
tags: ["antigravity", "concurrency", "state", "hooks", "data-loss"]
---

# b21de3c2: Serialize Antigravity advisory queue updates

## What was observed

`_queue_result()` reads one conversation queue, appends notes in memory, and
atomically replaces the file. `atomic_json()` protects file integrity but does
not lock the complete read-modify-write transaction. Concurrent PreToolUse or
PostToolUse hooks can read the same old list and replace it with divergent lists,
silently losing one detector's advisory context.

`PostInvocation` also reads and unlinks the queue without coordination with a
concurrent writer.

## Why it is a problem

Antigravity can invoke multiple subagents and tool calls concurrently. Losing an
advisory means the model never sees a valid security, quality, or workflow note,
even though every individual JSON file remains well formed.

## Why it is not a duplicate

- [#11ea7ba3](11ea7ba3-prevent-concurrent-memory-lost-updates.md) concerns
  persistent memory with a different store and conflict contract.
- [#88c16c9d](88c16c9d-verify-opencode-reminder-dispatch-race.md) concerns an
  OpenCode network/API dispatch race, not Antigravity file state.

## What probably needs to be done

1. Lock the entire queue update and drain transaction, or partition notes by a
   unique hook invocation and merge them during PostInvocation.
2. Preserve deduplication and `MAX_QUEUED_NOTES` under concurrency.
3. Prevent a drain from deleting notes committed after its snapshot.
4. Define stale-state cleanup without deleting active queue entries.
5. Keep state files private and bounded.

## Acceptance criteria

- A synchronized multi-writer test retains every distinct advisory up to the cap.
- Duplicate notes appear once under concurrent insertion.
- A concurrent drain and write cannot lose the later note.
- Queue ordering is deterministic or explicitly documented as unordered.
- No lock, temporary file, or stale queue residue remains after the test.

## Sources

- `adapters/antigravity-2/gates/mainframe_hook.py:215-230`
- `adapters/antigravity-2/gates/mainframe_hook.py:244-254`
- `adapters/antigravity-2/gates/mainframe_state.py:45-60`
- <https://antigravity.google/docs/subagents>
