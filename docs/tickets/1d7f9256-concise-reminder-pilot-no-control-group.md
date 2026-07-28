---
id: 1d7f9256
title: concise-reminder pilot (ADR 0084) is unvalidatable as designed — no control group
status: open
priority: medium
component: hooks
discovered: 2026-07-03
discovered-from: []
tags: ["telemetry", "measurement", "pilot", "concise-reminder"]
---

# 1d7f9256: concise-reminder pilot (ADR 0084) is unvalidatable as designed — no control group

## What was observed
Telemetry review after ~1 month (2026-06-04 → 2026-07-03): `concise_reminder`
has 510 events across 21 sessions, 37 fires, but only **10 sessions ran long
enough to complete an 8-turn cycle**. Each row logs `reply_chars` (last-assistant
prose length), `turns_since_reminder`, and `reminded`.

The apparent effect gradient runs *opposite* to the hypothesis — "fresh" replies
(`turns_since_reminder<=2`) average ~1213 prose chars vs "drifted" (`>=6`) ~951.
That reversal is a **survivorship/composition artifact, not a reminder effect**:
- `turns_since_reminder` is deterministic turn-position (`((turn-1) mod 8)+1`), not random.
- By absolute turn, replies are naturally longest at turns 1-2 (~1400 chars) and
  fall to ~500 by turns 8-9 — the normal open-long / execute-terse rhythm.
- Bucket `n` decays 106→37 across gap 1→8: short sessions (which end on a long
  wrap-up reply) only feed low gaps; only long execution-heavy sessions reach
  high gaps. Restricting to `turn>8` (2nd+ cycle) collapses the gradient to noise
  (508, 990, 651, 817, 1105, 897, 287, 952; n=5-21).

## Why it is a problem
The pilot cannot answer its own question — does re-injecting the concise rule
reduce verbosity? — because it **fires every 8 turns unconditionally**, so there
is no reminded-vs-not comparison. `reply_chars` is dominated by turn-position and
tool-vs-prose composition; the reminder is one un-isolable factor among several.
A month of clean data yields no verdict. ADR 0084 itself flagged this as "an
UNPROVEN salience bet … reply length is a noisy proxy" — this confirms it is not
just noisy but structurally unmeasurable in the current design.

## Why it is not a duplicate
- [#e501e2df](e501e2df-engagement-hook-overfires-on-nonproject-writes.md) — covers
  the `task-workflow-engagement` hook *overfiring* on non-project writes; this
  ticket is about the `concise-reminder` hook's *measurement design*. Related only
  in that both concern Stop-family pilot hooks.
- [#d245b10d](d245b10d-measure-advisor-via-transcript-parse.md) — covers measuring
  advisor use via transcript parse; different artifact, same "make a pilot
  measurable" theme.

## What probably needs to be done
- Convert to an A/B: on each eligible Stop turn, fire the note on a **random
  subset** (e.g. 50%) instead of every 8th turn, and log an `eligible`/`fired`
  flag. Then compare `reply_chars` of fired-vs-not turns **matched on absolute
  turn position** — a real control. (requires verification that Stop-hook RNG is
  acceptable and that per-session state still resets on SessionStart/compact.)
- Alternatively, alternate the whole pilot on/off by session and compare
  distributions of reply length at matched turn positions.
- Decide a stopping rule up front (min N fired turns per arm) so the verdict is
  not read off underpowered buckets like the current 10-session sample.
- Separate, smaller gap found in the same review: `task-workflow-engagement.py`
  emits **no** telemetry event, so its firing is entirely unmeasured
  (`memory-reminder.py` does `log_event("memory_reminder", …)`). Add an event if
  its effect is ever to be evaluated.

## Acceptance criteria
- `concise-reminder.py` logs a control flag distinguishing eligible-but-not-fired
  turns from fired turns; a query over the telemetry DB can compute mean/median
  `reply_chars` for each arm at matched turn positions.
- A documented power threshold (min fired turns) is recorded before any keep/kill
  verdict on the pilot.
- (optional, if scoped in) `task-workflow-engagement.py` emits a telemetry event
  on fire.

## Sources
- `plugin-dist/hooks/scripts/concise-reminder.py:105` (`_advance`, the
  turns-since-reminder metric) and `:187` (unconditional `should_remind` fire).
- `plugin-dist/hooks/scripts/task-workflow-engagement.py` — no `log_event` call.
- `plugin-dist/hooks/scripts/memory-reminder.py:100` — the logging pattern to mirror.
- `docs/decisions/0084-concise-reminder-stop-hook-pilot.md` — pilot's own "unproven bet" hedge.
- Telemetry DB `~/.claude/mainframe/telemetry/telemetry.db`, table `events`, `event='concise_reminder'`.
