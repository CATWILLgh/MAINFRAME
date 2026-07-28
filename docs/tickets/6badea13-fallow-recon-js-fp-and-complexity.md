---
id: 6badea13
title: fallow-quality-note flags skill recon.js as unused (FP) and their complexity backlog is unowned
status: open
priority: low
component: hooks
discovered: 2026-07-13
discovered-from: []
tags: ["fallow", "false-positive", "skills", "complexity"]
---

# 6badea13: fallow-quality-note flags skill recon.js as unused (FP) and their complexity backlog is unowned

## What was observed

The Stop-hook fallow quality note (2026-07-13, unrelated plugin-fix session)
reported for TS/JS:

- "9 unused source file(s)": `core/skills/{nestjs,nextjs,react}-*-patterns/recon.js`
  plus their `plugin-dist/` render copies (and 4 more).
- "8 critically complex function(s); worst: `detectAll` in
  `core/skills/react-frontend-patterns/recon.js` (22 lines, cyclomatic 19)".

## Why it is a problem

- The "unused" finding is a false positive class: skill `recon.js` scripts are
  executed at runtime by agents (`node recon.js` from the skill body), never
  imported — import-graph reachability cannot see them. Recurring FP noise
  trains readers to discount the fallow note (severity-inflation effect on an
  advisory channel).
- The complexity findings are real pre-existing debt, doubled by render copies
  (core + plugin-dist), and currently no ticket owns them — silent walk-past
  each session.

## Why it is not a duplicate

- [#e43819ea](e43819ea-length-gate-non-python-function-length.md) — covers
  extending the LENGTH gate to non-Python; this ticket is about the fallow
  analyzer's unused-file FP class and the existing complexity backlog in skill
  recon scripts.

## What probably needs to be done

- Teach `fallow-quality-note.py` (or its config) an exclusion/entry-point
  notion for runtime-executed scripts — e.g. treat `*/skills/*/recon.js` as
  entry points, or drop the unused-file dimension for paths matching skill
  supporting files. Requires verification against fallow's actual config
  surface.
- Also exclude `plugin-dist/` render copies from analysis (byte-copies of
  `core/`; double-reporting) — requires verification that the analyzer scope
  is configurable per path.
- Separately triage the 8 critical-complexity functions in skill recon
  scripts; `detectAll` (react) first. Refactor only with the skill's tests
  green (recon scripts have Python-side test precedent in `test_recon.py` for
  the python skill; JS recons may need a small harness first).

## Acceptance criteria

- A Stop-hook fallow note in this repo no longer lists skill `recon.js` files
  as unused, and does not double-report `plugin-dist/` copies.
- Complexity findings for recon scripts either resolved (refactor with tests)
  or explicitly accepted with rationale recorded here.

## Sources

- Stop-hook fallow note text, 2026-07-13 (this session).
- `plugin-dist/hooks/scripts/fallow-quality-note.py` — the advisory hook.
- `core/skills/react-frontend-patterns/recon.js` — `detectAll`, cyclomatic 19.
