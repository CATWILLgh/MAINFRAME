---
id: 9b2e6f41
title: "Skill-miss follow-up: analyze reminder incidents + skill_load, tune only proven-miss skill descriptions"
status: open
priority: medium
component: skills
discovered: 2026-06-10
discovered-from: []
tags: ["skills", "telemetry", "analytics", "descriptions"]
---

# 9b2e6f41: Skill-miss follow-up — analyze reminder incidents + skill_load, tune only proven-miss descriptions

## What was observed

Todo item "побуждать агентов активнее использовать скиллы" was triaged with telemetry (2026-06-10, window 06-04→06-10, 1008 events / 142 sessions): in substantive sessions (>10 events) skills DO load (10 of 11 sessions, ~2.7 loads each); 275 subagent dispatches deliver pattern skills via agent-definition preloads (invisible to `skill_load`). The unproven gap: six situational skills with no agent channel (`testing-strategy`, `severity-calibration`, `curl-requests`, `secrets-handling`, `ops-app-server-safety`, `code-audit`) had zero loads — but whether their trigger situations even occurred is unmeasurable without miss-signals.

Same day, the two non-blocking reminder hooks started logging `incident` telemetry rows on firing (`commit-conventional-reminder` → `rule_id: ai-trailer|non-conventional-subject|no-inline-message`; `bash-pattern-reminder` → per-pattern labels). A reminder firing = a recorded "situation occurred without the discipline applied" miss-proxy.

## Why it is a problem

Without this follow-up the new counters are write-only — collected ahead of a decision they were built to drive (the hub's own anti-vanity telemetry rule). The decision: which skill descriptions actually need trigger tuning, vs leaving them alone.

## Why it is not a duplicate

- [faa110d8](faa110d8-telemetry-detector-incident-wiring.md) — wiring `incident` into the ~11 SECURITY/quality gates (high-blast-radius, per-gate verification). This ticket consumed only the low-risk non-blocking reminder subset (2 hooks, shipped 2026-06-10) and is about the ANALYSIS + description tuning, not further wiring.
- [3f8a21bc](3f8a21bc-userpromptsubmit-denial-nudge-probe.md) — harness-feedback nudge channel probe; unrelated metric.

## What probably needs to be done

After ~2026-06-24 (≥2 weeks of data):

1. Query `~/.claude/mainframe/telemetry/telemetry.db` (physically `workspace/runtime/telemetry/` in the repo since 2026-06-11): `incident` rows by `hook`/`rule_id`/project; `skill_load` by skill; substantive-session denominator (>10 events, excluding the home-dir noise sessions).
2. Decide per signal:
   - `commit-conventional-reminder` misses high while `git-conventional-commits` loads low → tune that skill's `description`/`when_to_use` (situation-based triggers).
   - `bash-pattern-reminder` rules that keep firing → the fix is allowlist/helper/memory reinforcement, not a skill description.
   - Six zero-load situational skills: check `~/.claude/mainframe/feedback/` for related friction reports; no signal either way → leave them alone (no blind tuning).
3. Tune ONLY proven-miss descriptions (per official guidance, `name`+`description` are the sole triggering signals — code.claude.com/docs/en/skills). Re-measure after.

## Acceptance criteria

- Analysis recorded (numbers per hook/rule/skill, with the substantive-session denominator).
- Explicit per-skill verdict: tuned (diff) / no-change-justified.
- No description changed without a corresponding measured miss signal.

## Sources

- Telemetry queries + triage conclusions: session b1c19a40 (2026-06-10).
- `plugin-dist/hooks/scripts/commit-conventional-reminder.py`, `bash-pattern-reminder.py` — incident logging (shipped 2026-06-10).
- Official triggering mechanics: code.claude.com/docs/en/skills ("Claude will use these [name and description] when deciding whether to trigger the skill").
