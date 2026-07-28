---
id: 1e323eee
title: Codex skill projection relies on exact prose rewrites and emits stale safety claims
status: open
priority: medium
component: codex-layer
discovered: 2026-07-15
discovered-from: []
tags: ["codex", "architecture", "projection", "drift", "documentation"]
---

# 1e323eee: Codex skill projection relies on exact prose rewrites and emits stale safety claims

## What was observed

The Codex builder adapts shared skills through a long sequence of exact `str.replace()` and regular-expression rewrites. A source wording change can make a replacement stop matching without a build error. Current output demonstrates semantic drift: the generated secrets guidance says Codex Phase 1 has no path-validation or secret-commit hook even though those hooks are now delivered.

The representative golden preserves the stale statement, so snapshot agreement does not prove semantic correctness.

## Why it is a problem

Safety guidance can contradict the active runtime while all render checks remain green. Exact prose matching also makes harmless documentation edits an implicit adapter API with no declared contract.

## Why it is not a duplicate

- [#aee3901b](aee3901b-build-codex-over-400-lines.md) owns module and function size. Splitting the file does not remove text-coupled transformation semantics.

## What probably needs to be done

- Move runtime-specific claims into explicit adapter fragments or structured capability data.
- Make required transformations assert their match count and fail when source text drifts.
- Add semantic tests for safety capabilities rather than relying only on byte goldens.

## Acceptance criteria

- Generated Codex guidance accurately reflects all delivered security hooks.
- A changed or missing required transformation fails generation with the affected skill and rule named.
- Representative tests assert capabilities and constraints, not only exact generated prose.

## Sources

- `adapters/codex/build_codex.py:155-317`
- `dist/codex/skills-golden/secrets-handling/SKILL.md:121-122`
- `adapters/codex/gates/mainframe-hook.sh`
