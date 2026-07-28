---
id: 1dddee0b
title: Path-scoped Rules layer is hand-authored in dist/ — reconcile with the render-only neutral-core model
status: open
priority: low
component: architecture
discovered: 2026-07-15
discovered-from: []
tags: ["rules", "neutral-core", "architecture", "render"]
---

# 1dddee0b: Path-scoped Rules layer is hand-authored in dist/ — reconcile with the render-only neutral-core model

## What was observed
The path-scoped Rules layer (`~/.claude/rules/<name>.md`, `paths:`-frontmatter) is the
one layer authored DIRECTLY in `dist/claude-code/rules/<name>.md` and symlinked out — it
is NOT rendered from `core/`. Evidence: there is no `core/rules/`; it is absent from
`render_core.py` MAPPINGS; `install.sh` symlinks `dist/claude-code/rules/` out directly
(see the "like dist/claude-code/rules" comment). This contradicts the neutral-core
principle "never hand-edit `dist/`" (sources live in `core/` + `adapters/`). The layer is
currently EMPTY, so the contradiction is latent — no rule has been authored yet.

## Why it is a problem
Two smaller issues today, one larger tomorrow:
- **Doc contradiction:** the layer specs (`decision-tree.md` Recipe G, `rules.md`,
  `CONTRIBUTING.md`) now correctly document the exception, but a general "never hand-edit
  `dist/`" reader still meets an apparent contradiction. Documented, not resolved.
- **Tri-target gap:** Rules exist only for Claude Code. OpenCode and Codex have their own
  path/rule mechanisms; a `core/`-sourced Rules layer could project to all three, matching
  how skills/agents/gates/permissions already do. Hand-authoring in `dist/claude-code/`
  bakes in single-tool.
- **First-artifact trap:** whoever authors the first path-scoped rule inherits this
  unresolved model and may hand-edit a `dist/` file, or wrongly assume a `core/rules/`
  source exists.

## Why it is not a duplicate
- [#3cd20dc8](3cd20dc8-hub-semgrep-rules-dir-never-found.md) — about `core/gates/rules`
  (semgrep detector DATA), a different "rules" dir; not the path-scoped instruction layer.

## What probably needs to be done
Decide the Rules layer's model before its first artifact:
- **Option A** — keep it a documented hand-authored `dist/claude-code/rules/` exception
  (Claude-Code-only), and add a one-line carve-out to the "never hand-edit dist/" principle
  so the contradiction is explicit rather than apparent.
- **Option B** — introduce a `core/rules/` (+ `adapters/<tool>/` projection) source and a
  `render_core.py` mapping, so Rules render like every other layer and can reach OpenCode
  and Codex. **requires verification** that OpenCode/Codex have a path-scoped-rule analogue
  worth projecting into.

## Acceptance criteria
- A recorded decision (ADR or this ticket's resolution) on A vs B; docs and, if Option B,
  `render_core.py` + `core/rules/` updated so no doc says "never hand-edit dist/" while
  another says "author rules in dist/".

## Sources
- `docs/layers/rules.md`, `docs/layers/decision-tree.md` (Recipe G / M7)
- `tools/render_core.py` (no rules mapping), `install.sh` (direct rules symlink)
- Memory: hub-rules-layer-handauthored-exception
