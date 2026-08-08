---
id: 0e6ed5e7
title: Only Claude Code binds the capabilities the neutral brick names
status: open
priority: medium
component: adapters
discovered: 2026-08-08
discovered-from: []
tags: ["instructions", "adapters", "agnosticity", "bindings"]
---

# 0e6ed5e7: Only Claude Code binds the capabilities the neutral brick names

## What was observed

`core/instructions/agnostic.md` states four rules in terms of a capability rather than a tool:

- honour a reply language the runtime pins in its settings;
- verify a tool is available before relying on it;
- ask a decision-level question through a structured surface (this one lives in `orchestrator.md`);
- rely on permission rules where the runtime enforces credential handling mechanically.

`adapters/claude-code/instructions/50-bindings.md` and `62-orchestration-claude-code.md` name the concrete Claude Code surfaces. The other four adapters name none: `adapters/codex/instructions/90-runtime-codex.md` and `adapters/zcode-desktop/instructions/90-runtime-zcode-desktop.md` mention no equivalent at all, and OpenCode and Antigravity only touch the topic in passing.

This is **not a regression**. Before the 2026-08-08 restructure the rules carried an inline `(Claude Code: …)` parenthetical, which told an agent running under OpenCode or Codex nothing about its own runtime. The gap was always there; separating the bricks made it visible.

## Why it is a problem

A rule an agent cannot act on is close to no rule. "Verify tool availability up front" is actionable in Claude Code because `ToolSearch` is named; under Codex the agent is told to verify without being told how, so it either invents a method or skips the rule. The same holds for the pinned reply language and for permission-backed credential handling.

It also leaves the agnosticity principle half-applied: the neutral brick is genuinely neutral now, but the adapter brick that should absorb the specifics only exists for one of five targets.

## Why it is not a duplicate

- [#a7c96692](a7c96692-gate-mapping-drift-three-tools.md) — gate detector routing, a different layer.
- [#5c53fd0f](5c53fd0f-per-adapter-cross-layer-audit.md) — the umbrella sweep across all adapter layers; this is one named finding inside the instructions layer that can be closed on its own.

## What probably needs to be done

- For each of Codex, OpenCode, ZCode Desktop and Antigravity 2.x, establish whether the runtime actually has each of the four surfaces. Verify against the installed runtime or its own documentation — do not infer an equivalent from the Claude Code name.
- Where a surface exists, add it to that adapter's instruction fragment in the same shape as `50-bindings.md`.
- Where it does not exist, say so explicitly in that adapter's fragment rather than leaving silence, so an agent stops looking instead of improvising.
- Keep the asking binding with the orchestrator brick, not the delivered one: it moves to `mainframe-init` together with the rule it serves.

## Acceptance criteria

- Every capability named neutrally in `agnostic.md` and `orchestrator.md` either has a concrete binding in each adapter's fragment, or an explicit "this runtime has no equivalent" statement there.
- A test fails when the neutral bricks name a capability that some adapter neither binds nor explicitly disclaims.
- No adapter fragment names another runtime's tool.

## Sources

- `core/instructions/agnostic.md`, `core/instructions/orchestrator.md`
- `adapters/claude-code/instructions/50-bindings.md`, `adapters/claude-code/instructions/62-orchestration-claude-code.md`
- `adapters/{codex,opencode,zcode-desktop,antigravity-2}/instructions/90-runtime-*.md`
- `docs/principles.md` §1 — tool-agnosticity of the neutral core
