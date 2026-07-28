---
id: e5308bd1
title: Telemetry for OpenCode sessions — needs a source tag in the schema first
status: closed
priority: medium
component: opencode-layer
discovered: 2026-07-08
discovered-from: ["#b7a493b8"]
tags: ["opencode", "telemetry", "deferred"]
---

# e5308bd1: Telemetry for OpenCode sessions — needs a source tag in the schema first

## What was observed
The hook dispatcher (`opencode/plugins/mainframe-gates.js`) deliberately does
NOT map `telemetry.py`. The user wants OpenCode usage analyzed too ("как
по-другому анализировать"), explicitly deferred until the core layer works.

## Why it is a problem
Without OpenCode-side events the hub's telemetry answers only half the usage
picture. But mapping it naively would write OpenCode/GLM events into the same
SQLite with no source dimension — CC and OpenCode behavior would blend and
degrade every existing analysis.

## Why it is not a duplicate
[#b7a493b8](b7a493b8-opencode-plugin-port-security-hooks.md) is the gate/
advisory port; telemetry was explicitly carved out of it.

## What probably needs to be done
1. Schema first: add a `source` column (values: `claude-code`, `opencode`) to
   the telemetry events table + default backfill `claude-code`; thread a
   source field through `log_event` in `_hooklib.py`.
2. Then a dispatcher row (or a dedicated lightweight plugin hook) emitting the
   same event shapes with `source=opencode`. Note: OpenCode payloads lack
   `session_id`/`agent_type` CC fields — map from OpenCode's `sessionID`.
3. Update the hub-page Usage/Telemetry panels to facet by source.

## Acceptance criteria
- Existing CC telemetry queries return identical results (backfill verified).
- OpenCode session events appear tagged, and hub.html can filter by source.

## Sources
- `plugin-dist/hooks/scripts/telemetry.py`, `_hooklib.py` `log_event`
- User direction 2026-07-08: collect later, after the core works

## Progress note (2026-07-09)

Step 1 (schema first) landed: `events` gains `source TEXT DEFAULT
'claude-code'` (legacy DBs migrate via guarded `ALTER TABLE`, constant
default backfills old rows); `log_event` threads `hook_payload["source"]`
with the `claude-code` default. Tests: 3 new + schema contract updated.
Remaining: OpenCode dispatcher row emitting tagged events (set
`source: "opencode"` in `ccPayload`), hub-page facet by source.

## Resolution (2026-07-09)

**Implementer:** autonomous session (Fable 5)
**Commits:** `fcd2880` (schema + backfill), `7b33854` (dispatcher row),
plus the hub-page facet commit referencing this ticket.
**Summary:** all three ticket steps landed — `source` column with legacy
backfill; dispatcher's 12th advisory row shells `telemetry.py` with
`source: "opencode"`, `session_id` from OpenCode's `sessionID`, and
`hook_event_name`; hub page shows "Events by source" and survives
pre-migration DBs (guarded query).
**Claims to verify on audit:**
- `python3 tools/test_telemetry.py` — 17/17 (default/explicit source, legacy
  backfill).
- `node tools/test_mainframe_gates.mjs` — 14/14 incl. the tagged-spawn
  contract test.
- `.venv/bin/python3 tools/test_build_hub_page.py` — 24/24 incl. legacy-DB
  no-crash + by-source breakdown.
- OpenCode events appear tagged only after real OpenCode sessions run with
  the restarted plugin — machine-level observation, not CI-checkable.
