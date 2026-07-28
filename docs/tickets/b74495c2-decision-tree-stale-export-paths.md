---
id: b74495c2
title: Principles documentation references retired export and plugin-dist layouts
status: open
priority: low
component: docs
discovered: 2026-06-14
discovered-from: ["#001"]
tags: ["docs", "plugin-migration", "decision-tree", "layers"]
---

# b74495c2: Principles documentation references retired export and plugin-dist layouts

## What was observed

`docs/layers/decision-tree.md` still points readers to `export/` for skills and agents,
but those artifacts live in `plugin-dist/` after the plugin migration:
- `decision-tree.md:144` — "Grep in `export/CLAUDE.md` and `export/skills/**/SKILL.md`".
- `decision-tree.md:202` — "Create a subagent (`export/agents/<domain>.md`)".

Found while walking the decision tree to place a Python type-check capability — the
path references would send a future session to empty/wrong locations.

## Why it is a problem

Low severity — the layer LOGIC is correct; only the physical paths are stale. But the
decision-tree is the mandatory first stop for any new artifact (per hub CLAUDE.md "Hub
artifact placement"), so wrong paths there mislead every future placement walk.

## Why it is not a duplicate

[#001](001-agents-md-stale-plugin-migration.md) covers `docs/layers/agents.md` (the agents
layer doc). This is a different file (`decision-tree.md`) with the same migration-staleness
root cause. Worth checking the other `docs/layers/*.md` for the same `export/skills` /
`export/agents` pattern in one sweep.

## What probably needs to be done

- `rg -n 'export/(skills|agents)' docs/layers/` → update each hit to `plugin-dist/...`
  (skills → `plugin-dist/skills/`, agents → `plugin-dist/agents/`), keeping `export/CLAUDE.md`
  and `export/rules/` as-is (those genuinely stay in `export/`).
- Verify the same sweep against #001 so the two tickets close consistently.

## Acceptance criteria

- `rg 'export/skills|export/agents' docs/layers/decision-tree.md` returns nothing.
- No `docs/layers/*.md` points skills/agents at `export/` (cross-check with #001).

## Sources

- `docs/layers/decision-tree.md:144`, `:202`.
- Plugin migration context: ticket #001, memory `agents.md` placement notes.

## Resolution (2026-06-14)

Fixed in the docs/layers/ actualization. `decision-tree.md:144` now reads
`plugin-dist/skills/**/SKILL.md` and `:202` reads `plugin-dist/agents/<domain>.md`. The broader
sweep this ticket asked for ("check the other docs/layers/*") was done in the same change — all of
README/skills/agents/hooks/commands plus `docs/principles.md` actualized. `rg
'export/(skills|agents|hooks|commands)' docs/layers/` is clean. Acceptance criteria met.

## Reopened (2026-07-15)

The neutral-core migration replaced both former delivery layouts with `core/`, `adapters/<tool>/`, and `dist/<tool>/`, but `docs/principles.md` again contains the retired `export/` and `plugin-dist/` paths throughout its placement, language, and source-of-truth rules. The layer documents now carry a current three-tool architecture note, so the principle source they import contradicts the active repository structure.

### Updated acceptance criteria

- `docs/principles.md` describes authored sources under `core/` and `adapters/<tool>/` and rendered delivery under `dist/<tool>/`.
- No active architectural instruction routes a new artifact to `export/` or `plugin-dist/`.
- Historical ADR text remains historical and is not rewritten unless it is presented as current guidance.

### Current sources

- `docs/principles.md:3`, `docs/principles.md:9`, `docs/principles.md:28`, `docs/principles.md:34`
- `docs/principles.md:58-60`, `docs/principles.md:84-87`
