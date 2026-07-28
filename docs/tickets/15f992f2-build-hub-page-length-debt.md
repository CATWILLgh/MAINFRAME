---
id: 15f992f2
title: build_hub_page.py exceeds file and function length limits
status: open
priority: low
component: observability
discovered: 2026-07-15
discovered-from: []
tags: ["maintainability", "hub-page", "file-size", "function-size"]
---

# 15f992f2: build_hub_page.py exceeds file and function length limits

## What was observed

`tools/build_hub_page.py` is 768 lines. `_aggregate_usage()` spans lines 358-426 (69 lines), and `collect_delivery()` spans lines 537-604 (68 lines), exceeding the repository's function limit.

## Why it is a problem

Collection, graph construction, health analysis, usage aggregation, delivery modeling, and page serialization are coupled in one large observability generator. The incomplete Codex model demonstrates the cost of changing that structure safely.

## Why it is not a duplicate

- [#4f9a48cc](4f9a48cc-codex-observability-docs-incomplete.md) owns the missing Codex behavior; this ticket is a behavior-preserving structural split.

## What probably needs to be done

- Split source collectors, delivery modeling, graph/health analysis, usage aggregation, and serialization into focused modules.
- Preserve the existing output schema until a separately reviewed migration changes it.

## Acceptance criteria

- Each module is under 400 lines and each function under 60 lines.
- `tools/test_build_hub_page.py` and a representative generated-page comparison remain green.

## Sources

- `tools/build_hub_page.py:1-768`
- `tools/build_hub_page.py:358-426`, `tools/build_hub_page.py:537-604`
