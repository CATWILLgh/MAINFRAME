---
id: 001
title: docs/layers/agents.md stale after plugin migration (wrong paths + incomplete agent inventory)
status: closed
priority: low
component: docs
discovered: 2026-06-02
discovered-from: []
tags: ["docs", "layers", "plugin-migration"]
---

# 001: docs/layers/agents.md stale after plugin migration (wrong paths + incomplete agent inventory)

## What was observed
`docs/layers/agents.md` still describes the agents layer as it existed before the plugin migration:
- The "Where it lives" header and §2.1 reference `export/agents/<name>.md` and state the layer is "currently **empty** — reserved layer". The actual agents now live in `plugin-dist/agents/`.
- The §2.1 "Current agents" table lists only `web-search`. Six agents now exist in `plugin-dist/agents/`: `nestjs-backend-engineer`, `python-backend-engineer`, `react-frontend-engineer`, `decision-reviewer`, `web-search`, `devops-engineer`.

## Why it is a problem
The layer reference doc is the authoritative map for where agents live and which exist. A future session reading it would look in `export/agents/` (empty), conclude the layer is unused, and miss the six real agents — leading to wrong placement decisions or duplicated work. It violates the hub "supersede-not-append / single source of truth" discipline: the doc currently contradicts the repository.

## Why it is not a duplicate
First ticket in this project; no existing tickets matched `agents.md` / `export/agents` / `plugin migration`.

## What probably needs to be done
- Update "Where it lives" to point at `plugin-dist/agents/<name>.md` (the plugin path), keeping the `~/.claude` exposure note via the plugin mechanism.
- Rewrite the §2.1 "Current agents" table to list all current agents with purpose + activation, OR replace the static table with a pointer to `plugin-dist/agents/` to avoid re-staleness.
- Verify no other `docs/layers/*.md` carries the same `export/agents/` assumption.

## Acceptance criteria
- `docs/layers/agents.md` references `plugin-dist/agents/` and no longer claims the layer is "currently empty".
- The agent inventory reflects all agents present in `plugin-dist/agents/` at the time of the fix.
- `rg 'export/agents' docs/layers/` returns only intentional references (if any).

## Sources
- `docs/layers/agents.md:3` — "currently **empty** — reserved layer"
- `docs/layers/agents.md` §2.1 — "Current agents" table lists only `web-search`
- `plugin-dist/agents/` — actual agent files (6 present)

## Resolution (2026-06-14)

**Implementer:** MAINFRAME docs actualization session
**Commits:** `13ebb7f920a58fca97ed23f054fdbc1c8d60df6c`
**Summary:** The layer guide was updated to the then-current plugin layout,
the empty/reserved framing was removed, and §2.1 gained the live seven-agent
inventory. The ticket's original count of six predated
`nextjs-backend-engineer`.
**Claims to verify on audit:**
- The cited commit changes `docs/layers/agents.md` from `export/agents/` to
  the then-current `plugin-dist/agents/` location.
- The cited commit removes the empty/reserved/first-artifact framing.
- The cited commit lists seven agents, including `nextjs-backend-engineer`.
- At that revision, `rg 'export/agents' docs/layers/` is clean.
