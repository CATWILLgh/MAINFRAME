---
id: e0f591b1
title: Enforce memory bounds during physical file reads
status: open
priority: medium
component: portable-memory
discovered: 2026-07-15
discovered-from: []
tags: ["memory", "performance", "resource-bounds", "resilience"]
---

# e0f591b1: Enforce memory bounds during physical file reads

## What was observed

`load_memory()` calls `read_bytes()`, decodes the complete file, splits all
lines, and re-encodes it before applying the 25 KiB and 200-line context bounds.
`check_memory()` also reads and decodes the entire file. A controlled 64 MiB
`MEMORY.md` returned bounded context but peaked at 222,543,872 bytes RSS.

Both adapters invoke the loader repeatedly during model-context injection, so a
manually edited or corrupted oversized file repeats this cost.

## Why it is a problem

The public contract promises bounded memory loading, but only the returned text
is bounded. A large file can stall the hook, hit adapter timeouts, exhaust memory,
and silently remove project recall from every invocation.

## Why it is not a duplicate

- [#11ea7ba3](11ea7ba3-prevent-concurrent-memory-lost-updates.md) covers stale
  writer conflicts, not read amplification.
- [#2a665dde](2a665dde-validate-memory-version-on-read.md) covers store metadata.

## What probably needs to be done

1. Read only enough bytes and lines to construct the bounded injected index.
2. Detect truncation without decoding the complete remainder.
3. Use `stat()` for byte count and chunked line counting for explicit checks.
4. Preserve UTF-8 code-point safety at the byte boundary.
5. Define a separate bounded strategy for topic files and malformed UTF-8.

## Acceptance criteria

- Loading a 64 MiB fixture has memory use proportional to the configured bound,
  not to file size.
- The first 200 lines or 25 KiB match existing behavior byte-for-byte.
- UTF-8 split-boundary, no-final-newline, very-long-line, and invalid-UTF-8 tests
  cover both `load` and `check`.
- Oversized input still emits the current explicit truncation warning.
- Antigravity and OpenCode adapter timeout tests remain comfortably below budget.

## Sources

- `core/memory/store.py:157-195`
- `core/memory/store.py:223-242`
- `tools/test_memory_store.py:84-110`
- <https://code.claude.com/docs/en/memory>
