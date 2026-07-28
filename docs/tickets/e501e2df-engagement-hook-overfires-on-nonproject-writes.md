---
id: e501e2df
title: task-workflow-engagement nudges on non-project writes (~/.claude/ memory, plans)
status: closed
priority: low
component: hooks
discovered: 2026-06-13
discovered-from: []
tags: ["hooks", "task-workflow-engagement", "false-positive"]
---

# e501e2df: task-workflow-engagement nudges on non-project writes (~/.claude/ memory, plans)

## What was observed
`task-workflow-engagement.py` fires its "invoke task-workflow first" nudge on the first
Edit/Write/MultiEdit of a session segment. It fired repeatedly this session on writes to
`~/.claude/projects/.../memory/*.md` (auto-memory notes) — which are not project code /
config / docs in the task-workflow sense. The nudge's intent is "load the process before
modifying *work*", not before jotting a memory note or a plan file.

## Why it is a problem
Minor — the hook is advisory, fires once per segment, never blocks. But it is a
false-positive: memory/plan writes don't warrant the task-workflow cycle, and a nudge that
cries wolf on housekeeping writes erodes the signal for real modifying work. No correctness
impact; pure adherence-signal hygiene.

## Why it is not a duplicate

No other ticket covers the engagement reminder consuming its once-per-segment
state on writes outside the active project.

## What probably needs to be done
In `task-workflow-engagement.py`, skip the nudge when the `file_path` is outside the
project — e.g. under `~/.claude/`, the plans dir, or `$CLAUDE_PROJECT_DIR`-external paths.
Cheap path check before `emit_note`. Keep it conservative (only clearly-non-project paths)
to avoid suppressing a real in-project doc edit. Add a Tier-1 test: a `~/.claude/...` Write
does not nudge; an in-project Write still does.

## Acceptance criteria
- A Write whose target is under `~/.claude/` (memory, plans) does not emit the nudge.
- An in-project modifying Write still nudges (no regression to the core behaviour).
- `test_task_workflow_engagement.py` covers both; suite stays green.

## Sources
- `core/gates/detectors/task-workflow-engagement.py` (the `MODIFY_TOOLS` branch, before `emit_note`).
- Observed: this session, nudge fired on memory-file writes under `~/.claude/projects/.../memory/`.

## Re-occurrence noted (2026-06-18)

**Noticed during:** harness-feedback report `20260618-082601-MAINFRAME` — same sighting from a later session (nudge on a Write to the auto-memory dir after a SessionStart:resume reset).
**Where:** same code path; no new component.
**Additional details:** the report adds the segment-reset angle — the memory write was the first Edit/Write of the fresh segment, so the false fire also consumed the once-per-segment reminder.

## Resolution (2026-07-03)

**Implementer:** main-session agent (feedback-queue processing)
**Commits:** 48c755a1781c44ded60fb6b52f7a19a368ecf6d8
**Summary:** Added `_in_project` guard before the nudge: a target resolving
outside the payload `cwd` returns silently WITHOUT consuming the
once-per-segment reminder (it stays armed for the first real in-project
write). Missing path/cwd or resolution errors keep the old behavior
(fail-open). Tests added per the acceptance criteria.
**Claims to verify on audit:**
- `tools/test_task_workflow_engagement.py` passes 13/13, including: out-of-project write silent + state stays `fresh` + subsequent in-project write still reminds; `/tmp` write silent; in-project relative path reminds.
- Full tools/ suite green at 48c755a.
- `_in_project` fail-open: payload without `cwd` (all pre-existing tests) behaves exactly as before the change.
