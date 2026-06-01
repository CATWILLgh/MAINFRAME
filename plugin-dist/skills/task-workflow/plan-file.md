# Plan / audit file

Loaded from `task-workflow` Step 3 when a task crosses the plan-file threshold (≥ 3 dependent phases, or ≥ 3 edge-cases / risks worth tracking).

## Two paths — do not conflate

| Role | Path | Owner | Lifetime |
|---|---|---|---|
| Tool plan file (interactive `EnterPlanMode` only) | `~/.claude/plans/<random-kebab-slug>.md` — flat, no date | Claude Code tool (path injected via plan-mode system message) | Single session; tool may reuse / replace |
| Hub audit copy (always) | `~/.claude/plans/audit/<basename(cwd)>/<YYYY-MM-DD>-<topic>.md` — hierarchical, dated | This skill | Persistent across sessions; audit trail |

Verified against Claude Code plan mode (2026-05-30): the tool path is flat with a random slug; the hub audit copy lives under `audit/` so it never collides. `<basename(cwd)>` from `basename "$(pwd)"` (no per-project config); `<topic>` is a ≤ 6-word kebab slug. `mkdir -p` the dir; the audit copy is never tracked by git.

## Format

```markdown
# <Topic title>

> Project: <basename(cwd)> · Date: <YYYY-MM-DD>
> Type: <feature|fix|refactor|migration|ops|docs> · Mode: <interactive|auto>

## Context
[Why — the problem/need, what prompted it, intended outcome. 1-3 sentences.]

## Recommended approach
[The chosen approach (not all alternatives), at a high level.]

## Critical files
- `path` — what changes / what is reused

## Phases
1. <phase> — [files] — [depends on previous? y/n]

## Risks
- <risk>: <mitigation>

## Verification
[How to test end-to-end: commands, MCP tools, tests.]

---
## What actually happened (filled retroactively)
[Deviations and why; surprises; what cost more / less.]
```

## Interactive vs auto

- **Interactive** — tool plan mode's 5 phases: `EnterPlanMode` → Explore agents (1-3) → Plan agents (1-3) → Review (read critical files, `AskUserQuestion`) → Write (into **both** the tool plan file and the hub audit copy) → `ExitPlanMode` for approval.
- **Auto** — same Phase 1-4 without the tool: skip `EnterPlanMode`; Explore + Plan still run; Review is internal reasoning; Write only the hub audit copy; then proceed (no `ExitPlanMode`).
