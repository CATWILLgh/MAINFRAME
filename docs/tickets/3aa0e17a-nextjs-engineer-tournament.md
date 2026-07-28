---
id: 3aa0e17a
title: Tournament-calibrate model/effort for nextjs-backend-engineer
status: open
priority: low
component: agents
discovered: 2026-06-04
discovered-from: []
tags: ["agents", "calibration", "nextjs", "tech-debt"]
---

# 3aa0e17a: Tournament-calibrate model/effort for nextjs-backend-engineer

## What was observed

ADR 0074 created `nextjs-backend-engineer` with `model: sonnet` / `effort: medium` **mirrored** from the sibling backend agents, NOT calibrated by a tournament for this agent's actual prompt body. The sibling agents (`nestjs-backend-engineer`, `react-frontend-engineer`) each record a 6-variant × 10-round tournament result backing their pick; this one does not yet.

## Why it is a problem

The model/effort claim in the agent body is currently an assumption ("mirror the siblings"), not evidence — the hub's convention is that a new file-based agent is calibrated empirically via the `agent-tournament` skill. `sonnet`/`medium` is a reasonable default but unverified for the Next.js prompt (which has its own recon dimensions, caching/version-sensitivity, and the server/client boundary discipline).

## Why it is not a duplicate

[#68fef6fb](68fef6fb-react-frontend-engineer-retournament.md) asks whether a
previously calibrated React agent must be re-tested after its prompt gained
`frontend-design` wiring. This ticket owns the first empirical calibration of
the distinct Next.js backend agent, whose initial model/effort choice was only
mirrored from siblings and has no baseline tournament.

## What probably needs to be done

- Run the `agent-tournament` skill against `nextjs-backend-engineer`: a variant matrix (e.g. sonnet × {low, medium, high}, haiku × medium), 5-6 Next.js verification queries with known-good answers (a Route Handler with caching, a Server Action with authz, a Prisma-singleton question, a caching-default-15 question, a boundary "is this server or client" question), ≥3 rounds.
- Score on plan reasoning + execution + Phase-H format adherence; pick the winner; update `model`/`effort` and the calibration note in the agent frontmatter/body.

## Acceptance criteria

- Tournament run recorded; `model`/`effort` confirmed or updated with the result; the "mirrored, not calibrated" note in the agent replaced by the tournament outcome.

## Sources

- `plugin-dist/agents/nextjs-backend-engineer.md` (the calibration note).
- ADR 0074 — `docs/decisions/0074-nextjs-backend-engineer.md`.
- `agent-tournament` skill (`.claude/skills/agent-tournament/`).
