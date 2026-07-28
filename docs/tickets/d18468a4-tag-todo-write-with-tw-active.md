---
id: d18468a4
title: Tag todo_write telemetry with tw_active to isolate task-workflow-seeded checklists
status: closed
priority: medium
component: hooks
discovered: 2026-06-13
discovered-from: []
tags: ["telemetry", "task-workflow", "pilot", "measurement", "adr-0082"]
---

# d18468a4: Tag todo_write telemetry with tw_active to isolate task-workflow-seeded checklists

## What was observed
ADR 0082 wires a `TodoWrite` checklist into task-workflow Step 3 (pilot) and logs a
`todo_write` telemetry event (counts only) to measure adoption. An advisor review found
the instrumentation cannot discharge the ADR's exit criterion #1 ("adoption on ≥3-phase
task-workflow tasks"): `todo_write` fires on EVERY TodoWrite from any agent/project, so the
logged volume is global todo usage, not "task-workflow-seeded checklists". The signal is
confounded — raw volume, not adoption.

## Why it is a problem
A pilot whose exit criterion its own telemetry can't answer reaches the 2026-07-11 review
unable to honestly close — permanent ceremony on a core skill that can't prove it earns its
place (the behavior-vs-quality trap `structured-workflow-efficacy-evidence` warns about).
ADR 0082's wording was corrected to state criterion #1 as raw volume pending this ticket;
this ticket is what makes it a real adoption signal.

## Why it is not a duplicate

[#faa110d8](faa110d8-telemetry-detector-incident-wiring.md) concerns incident
events emitted by security and quality detectors; [#40654275](40654275-telemetry-enable-canblock-events.md)
concerns enabling three Claude Code lifecycle event registrations; and
[#e5308bd1](e5308bd1-opencode-telemetry-source-tag.md) concerns distinguishing
Claude Code from OpenCode in the telemetry schema. This ticket instead adds
one task-workflow-engagement dimension to the existing `todo_write` event, so
none of those tickets can satisfy its adoption-measurement criterion.

## What probably needs to be done
Tag each `todo_write` event with whether task-workflow was engaged this session segment:
- The `task-workflow-engagement` hook already writes a per-segment marker (`active` /
  `reminded` / `fresh`) at a tempfile keyed by `session_id`. `telemetry.py`'s `todo_write`
  branch can read that state and record `tw_active: (state == "active")`.
- **Do it DRY, not via a duplicated path computation** (avoid the silent cross-hook
  dependency): move the marker dir + key + read into a single `_hooklib` helper
  (`tw_engagement_state(session_id)`), have BOTH `task-workflow-engagement.py` (its reads)
  and `telemetry.py` use it. One owner of the marker format.
- Update `test_task_workflow_engagement.py` (patch the `_hooklib` marker dir instead of the
  module-local one) and add a `telemetry` test: marker `active` → `tw_active: true`, absent
  → `false`. Privacy unchanged (no todo content, no paths).

Criterion #2 ("dropped-step incidents fall") has NO telemetry source — there is no
"step skipped" event. That stays manual / impression unless a separate step-completion
event is designed (larger, out of scope here).

## Acceptance criteria
- `todo_write` payload carries `tw_active`; `_hooklib` is the single owner of the marker
  read (no duplicated path logic across the two hooks).
- Tier-1 tests cover `tw_active` true/false; existing engagement + telemetry suites stay green.
- No privacy regression (counts + boolean only).

## Sources
- `docs/decisions/0082-todo-checklist-task-workflow-pilot.md` (the pilot + corrected criteria).
- `plugin-dist/hooks/scripts/telemetry.py` (`todo_write` branch), `task-workflow-engagement.py` (marker), `_hooklib.py` (proposed helper home).
- Memory `structured-workflow-efficacy-evidence`, `todowrite-tool-mechanics`.

## Resolution (2026-07-09)

**Implementer:** autonomous session (Fable 5)
**Commits:** `2cbfa4e3f9eb8cd918a8d0cf3bf9617125089d32`
**Summary:** marker format now has a single owner — `_hooklib` exports
`TW_ENGAGE_STATE_DIR` / `tw_engagement_path` / `tw_engagement_state`; the
engagement gate writes through them, `telemetry.py`'s `todo_write` branch
reads the state and records `tw_active: (state == "active")`. Both suites
patch the one `_hooklib` dir. Criterion #2 of ADR 0082 (dropped-step
incidents) remains without a telemetry source, per this ticket's own scoping.
**Claims to verify on audit:**
- `python3 tools/test_telemetry.py` — 18/18 incl. marker-active tagging and
  the exact-payload contract with `tw_active: false` by default.
- `python3 tools/test_task_workflow_engagement.py` — 13/13 via the shared
  `_hooklib` patch point.
- No duplicated marker-path computation: `grep -rn 'mainframe-tw-engage'
  core/gates/detectors/` matches only `_hooklib.py`.
