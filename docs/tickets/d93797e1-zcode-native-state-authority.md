---
id: d93797e1
title: Define neutral authority before projecting ZCode browser and native state
status: open
priority: medium
component: zcode-desktop
discovered: 2026-08-05
discovered-from: []
tags: ["zcode", "browser", "memory", "authority"]
---

# d93797e1: Define neutral authority before projecting ZCode browser and native state

## What was observed
ZCode Desktop provides browser control, project memory, checkpoints, fork and rewind, side conversations, and an internal desktop protocol. MAINFRAME currently has no neutral contract that separates browser read/write authority or defines ownership of runtime-managed memory and session databases.

The v1 adapter diagnoses these surfaces only and does not copy, enable, clear, or automate them.

## Why it is a problem
Projecting them from one adapter today would grant host-specific authority, duplicate opaque runtime state, or couple MAINFRAME to an undocumented desktop protocol.

## Why it is not a duplicate
No existing ticket defines a cross-adapter browser authority contract or ZCode runtime-state ownership.

## What probably needs to be done
Introduce a neutral capability only after a concrete cross-runtime use case exists. Separate browser read/write and local/external authority. Treat native memory and sessions as runtime-owned unless a documented export contract and explicit user operation justify otherwise.

## Acceptance criteria
- A neutral authority model exists for every projected browser action.
- Runtime-owned memory and session state remain untouched by ordinary install/update/uninstall.
- Any desktop protocol dependency is documented as stable by Z.ai and covered by compatibility probes.
- Tests prove that projected agents cannot gain broader browser authority than their neutral contract requests.

## Sources
- `adapters/zcode-desktop/capabilities.json`
- https://zcode.z.ai/en/docs/agents
