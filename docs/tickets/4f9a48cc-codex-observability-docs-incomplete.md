---
id: 4f9a48cc
title: Hub inventory, tests, and contracts still model only two delivery targets
status: open
priority: medium
component: observability
discovered: 2026-07-15
discovered-from: []
tags: ["codex", "observability", "documentation", "inventory", "test-gap"]
---

# 4f9a48cc: Hub inventory, tests, and contracts still model only two delivery targets

## What was observed

Codex is a live third adapter, but the hub inventory labels shared skills and agents as `both`, emits delivery records only for Claude Code and OpenCode, and exposes only an OpenCode installation command. The tests assert that two-tool model. ADR 0086 remains `proposed`, and the gate contract says it has two consumers.

The missing-detector launcher diagnostic is tracked in [#b86bf383](b86bf383-codex-gates-v1-followups.md); this ticket covers repository-wide status and inventory truth.

## Why it is a problem

The project's own architectural map and contract documentation under-report a deployed target. Reviews and future changes can therefore omit Codex while all current inventory tests remain green.

## Why it is not a duplicate

- [#a7c96692](a7c96692-gate-mapping-drift-three-tools.md) covers detector routing parity, not repository inventory or ADR lifecycle.
- [#b86bf383](b86bf383-codex-gates-v1-followups.md) covers runtime gate follow-ups, not the hub page data model.

## What probably needs to be done

- Replace the binary tool tag with an explicit target set or capability-to-delivery mapping.
- Add Codex umbrella, projection, hooks, rules, agents, and installation records to hub inventory.
- Update ADR and gate-contract status only after verifying the live implementation against their decisions.

## Acceptance criteria

- Hub inventory and its tests represent Claude Code, OpenCode, and Codex without an ambiguous `both` sentinel.
- Codex install and delivery artifacts appear in generated hub data.
- ADR 0086 and `core/gates/CONTRACT.md` state the current verified lifecycle and consumer set.

## Sources

- `tools/build_hub_page.py:90-128`, `tools/build_hub_page.py:537-604`
- `tools/test_build_hub_page.py:475-506`
- `docs/decisions/0086-codex-adapter.md:1-9`
- `core/gates/CONTRACT.md:1-9`
