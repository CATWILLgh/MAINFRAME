---
id: 84b2d271
title: Neutral permissions source is encoded in Claude Code command-pattern dialect
status: open
priority: medium
component: permissions-architecture
discovered: 2026-07-15
discovered-from: []
tags: ["architecture", "permissions", "claude-code", "opencode", "codex", "projection"]
---

# 84b2d271: Neutral permissions source is encoded in Claude Code command-pattern dialect

## What was observed

`core/permissions/rules.json` is presented as the neutral source of truth, but its entries are Claude Code strings such as `Bash(git add *)`, `WebFetch(domain:...)`, and MCP tool identifiers. Both non-Claude adapters reverse-parse those strings into their own models. The Codex parser already produced the invalid-decision defect tracked in [#95878fc4](95878fc4-codex-rules-invalid-deny-decision.md), while many entries are omitted by design.

## Why it is a problem

Tool-neutral policy cannot be reasoned about or validated independently of one target's syntax. Every adapter duplicates a partial parser, semantic omissions are easy to hide in summary counts, and target changes can turn a valid core file into invalid or weaker output.

## Why it is not a duplicate

[#95878fc4](95878fc4-codex-rules-invalid-deny-decision.md) is the immediate Codex syntax failure. [#a7c96692](a7c96692-gate-mapping-drift-three-tools.md) covers duplicated gate wiring. This ticket covers the upstream permission data model and projection boundary.

## What probably needs to be done

- Define a neutral structured command-policy schema with explicit action, matcher, decision, and target-support metadata.
- Render Claude Code, OpenCode, and Codex dialects from that schema rather than parsing Claude strings backwards.
- Make unsupported semantics explicit and fail on any omitted security rule unless the omission is recorded and approved.

## Acceptance criteria

- No adapter parses another adapter's permission string format.
- Each core rule has tested projections or an explicit unsupported disposition for every target.
- Native validators accept every generated policy.
- Cross-adapter tests prove equivalent decisions for a shared command corpus.

## Sources

- `core/permissions/rules.json:1-140`
- `adapters/opencode/build_opencode.py:150-193`
- `adapters/codex/build_codex.py:525-637`
- `docs/principles.md:7-9`, `docs/principles.md:80-87`
