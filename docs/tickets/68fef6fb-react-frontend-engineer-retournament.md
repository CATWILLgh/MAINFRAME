---
id: 68fef6fb
title: Re-tournament react-frontend-engineer model/effort after frontend-design skill wiring
status: open
priority: low
component: agents
discovered: 2026-06-03
discovered-from: []
tags: ["agents", "calibration", "tech-debt", "frontend-design"]
---

# 68fef6fb: Re-tournament react-frontend-engineer model/effort after frontend-design skill wiring

## What was observed

ADR 0071 added a third preloaded skill (`frontend-design`) to `plugin-dist/agents/react-frontend-engineer.md` plus a Phase-D dispatch bullet and a Phase-G verification bullet. The agent's own discipline note (`react-frontend-engineer.md` line ~110) states: *"Model + effort (`sonnet` / `medium`) are calibrated via 6-variant × 10-round tournament … Re-tournament after a notable prompt-body change."*

The change is **additive knowledge wiring** (a new dispatch target + verification items), not a restructure of the agent's reasoning flow — so the `sonnet` / `medium` winner is very likely still optimal. But "notable" is a judgment call, and the deferral is recorded here rather than decided silently.

## Why it is a problem

The calibration claim in the agent body now references a prompt body that grew since the tournament was run. If the addition shifts the plan-reasoning / execution balance (unlikely but unverified), the model/effort pick could be stale. Leaving it unflagged would let the "calibrated via tournament" claim drift from the actual prompt.

## Why it is not a duplicate

[#3aa0e17a](3aa0e17a-nextjs-engineer-tournament.md) covers the initial
calibration of `nextjs-backend-engineer`, whose model and effort were copied
from sibling agents without any tournament of its own prompt. This ticket
covers a re-tournament of the already-calibrated `react-frontend-engineer`
after its prompt gained `frontend-design` wiring. The agents, baselines and
questions under test are different, so completing either tournament would not
resolve the other.

## What probably needs to be done

- Re-run the 6-variant × 10-round tournament (same harness as the original) against the current agent body, with a representative React task set. (requires the tournament harness — out of scope for ADR 0071.)
- Compare perfect-run rate / avg quality / Phase-H compliance vs the recorded baseline (sonnet-medium: 8/10 perfect, 2.70/3.00, 100% format).
- If `sonnet` / `medium` still wins → update the note's "last re-tournamented" marker. If not → update `model:` / `effort:` and the note.

## Acceptance criteria

- Tournament re-run recorded; winner confirmed or `model`/`effort` updated in the agent frontmatter.
- The calibration note reflects the current prompt body.

## Sources

- `plugin-dist/agents/react-frontend-engineer.md` (calibration note, `skills:`, Phase D / G).
- ADR 0071 — `docs/decisions/0071-frontend-design-skill.md`.
