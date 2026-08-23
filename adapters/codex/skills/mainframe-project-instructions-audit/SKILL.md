---
name: mainframe-project-instructions-audit
description: Audit an existing project's Codex instruction hierarchy for conflicts, duplication, stale routing, and context bloat after the user explicitly requests maintenance. Use only for the deliberate audit run, not for ordinary code review.
---

# Audit project instructions

Audit the instruction system that Codex actually receives. Start read-only and
separate objective defects from choices that require the user.

## Reconstruct the effective system

1. Resolve the repository root and representative working directories.
2. Inspect the inherited global instruction file without modifying it.
3. Discover project `AGENTS.md`, `AGENTS.override.md`, configured fallback files,
   project skills, custom agents, and their direct instruction references.
4. For every materially different working directory, reconstruct the exact
   root-to-directory chain and note which file wins at each level.
5. Record lines, bytes, and the estimated combined instruction footprint for
   every always-loaded chain.

Check for:

- contradictory requirements, authority, ownership, or workflow rules;
- exact and semantic duplication across root, project skill, nested files, and
  agent instructions;
- broad rules stored in a narrow subtree, or local rules stored globally;
- an `AGENTS.md` hidden by an `AGENTS.override.md` in the same directory;
- broken links, missing skills or agents, stale names, and unreachable guidance;
- a project skill that repeats the full MAINFRAME catalogue instead of keeping
  a relevant project map;
- nested files that restate inherited guidance rather than add a local delta;
- excessive always-loaded text that can move to a linked reference without
  making required behavior implicit.

Do not use a universal line target as a quality score. Product limits are hard
ceilings; below them, judge text by whether it changes agent behavior enough to
justify permanent context cost.

## Reconcile safely

Report findings by practical effect and identify the owning source. Mechanical
defects such as a broken path or exact duplicate may have an obvious repair.
Any semantic conflict, removal of a unique rule, or ownership change requires
the user's decision before editing.

After the user accepts a cleanup, apply only that cleanup. Preserve unrelated
work and do not redesign the repository during maintenance.

## Verify and report

Reconstruct the affected chains again and report:

- what was removed, moved, or clarified and why;
- the before and after footprint;
- all remaining conflicts, stale references, or uncertain owners;
- which directories were covered;
- that static structure passed, without claiming that runtime routing or skill
  use was proven.

In development mode, the explicit skill invocation is recorded without prompt
text. Use its project, session, and timestamp to correlate later runtime events
when evaluating whether the cleaned instruction system actually helped.
