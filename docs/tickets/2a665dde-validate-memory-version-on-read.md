---
id: 2a665dde
title: Validate the memory store version on load and check
status: open
priority: medium
component: portable-memory
discovered: 2026-07-15
discovered-from: []
tags: ["memory", "versioning", "compatibility", "validation"]
---

# 2a665dde: Validate the memory store version on load and check

## What was observed

Only `write_memory()` validates `.mainframe-memory-version`. With an initialized
store changed to version `999`, `check_memory()` returned `valid=True` and
`load_memory()` injected the existing content, while a subsequent write correctly
failed with `unsupported memory store version: '999'`.

The architecture document states that unknown or corrupt metadata fails closed
for writes and fails open for context injection, but the current reader treats
the incompatible store as current data.

## Why it is a problem

A future schema or damaged marker can be read under the wrong interpretation.
`check` also reports a false clean result, preventing the agent from diagnosing
why writes fail. Read and write sides disagree about the same store contract.

## Why it is not a duplicate

- [#e0f591b1](e0f591b1-bound-memory-file-reads.md) concerns resource usage.
- [#11ea7ba3](11ea7ba3-prevent-concurrent-memory-lost-updates.md) concerns
  concurrent revisions, not the on-disk format version.

## What probably needs to be done

1. Centralize marker parsing and validation for load, check, and write.
2. Treat an absent marker on a truly uninitialized store separately from an
   initialized store with missing or corrupt metadata.
3. Return empty injected context for unsupported versions.
4. Make `check` return a machine-readable invalid-version error.
5. Define the migration boundary before introducing version 2.

## Acceptance criteria

- Unknown, empty, malformed, missing-after-initialization, and unreadable markers
  are covered by `load`, `check`, and `write` tests.
- Unsupported stores inject no memory and do not create or mutate filesystem state.
- `check` reports `valid=false` with the observed and supported versions.
- A normal version-1 store retains existing behavior.
- The contract document and JSON command payload describe the same semantics.

## Sources

- `core/memory/store.py:19-23`
- `core/memory/store.py:157-175`
- `core/memory/store.py:223-242`
- `core/memory/store.py:295-315`
- `docs/layers/memory.md:85-95`
