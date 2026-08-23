---
name: project-instructions-audit
description: Audit an existing project's Claude Code instruction hierarchy for conflicts, duplication, stale routing, and context bloat after the user explicitly requests maintenance.
argument-hint: "[optional scope]"
disable-model-invocation: true
---

# Audit project instructions

Audit the instruction system Claude Code actually receives. Start read-only and
separate objective defects from choices that require the user.

## Reconstruct the effective system

1. Resolve the repository root and representative working directories.
2. Inspect inherited user instructions without modifying them.
3. Discover root and nested `CLAUDE.md`, `.claude/CLAUDE.md`,
   `CLAUDE.local.md`, `.claude/rules/`, project skills, project agents, and
   their direct instruction references.
4. Reconstruct the startup set and every materially different lazily loaded
   subtree set.
5. Record lines, bytes, and estimated context cost for each set.

Check for contradictory requirements, authority or ownership; exact and
semantic duplication; incorrectly scoped rules; broken links; missing skills or
agents; stale names; a project skill that repeats the full MAINFRAME catalogue;
nested files that only restate inherited guidance; and always-loaded text that
can become a linked reference without hiding required behavior.

Do not use a universal line target as a quality score. Product limits are hard
ceilings; below them, keep only text whose behavioral value justifies its
context cost.

## Reconcile safely

Report each finding by practical effect and owning source. Mechanical defects
such as an exact duplicate or broken path can have an obvious repair. Any
semantic conflict, removal of a unique rule, or ownership change requires the
user's decision before editing.

After the user accepts a cleanup, apply only that cleanup. Preserve unrelated
work and do not redesign the repository during maintenance.

## Verify and report

Reconstruct the affected startup and subtree sets again. Report what changed,
the before and after footprint, remaining conflicts or uncertain owners, and
the directories covered. Do not claim that a clean static structure proves
runtime routing or proactive skill use.

In development mode, this explicit command is recorded without prompt text.
Use its project, session, and timestamp to correlate later runtime events when
evaluating the effect of the maintenance run.
