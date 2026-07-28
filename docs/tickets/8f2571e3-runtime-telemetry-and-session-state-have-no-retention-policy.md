---
id: 8f2571e3
title: Runtime telemetry and per-session state have no retention policy
status: open
priority: low
component: runtime-state
discovered: 2026-07-15
discovered-from: []
tags: ["performance", "telemetry", "state", "retention", "opencode"]
---

# 8f2571e3: Runtime telemetry and per-session state have no retention policy

## What was observed

The telemetry sink appends indefinitely to a SQLite events table. Engagement state creates per-session files under the temporary directory without expiry. The OpenCode dispatcher keeps `sessionState` entries until a later clean idle scan for that same session; a session that closes while findings remain has no explicit deletion path.

On the current machine the telemetry database contained 17,023 rows and occupied about 3.2 MB, while 151 engagement-state files occupied about 604 KB. These sizes are modest today but demonstrate monotonic accumulation.

## Why it is a problem

Long-lived global tooling gradually accumulates disk state and in-process map entries across projects and sessions. Without an explicit retention contract, growth is bounded only by user behavior and process restarts, and old diagnostic data may outlive its stated purpose.

## Why it is not a duplicate

[#4923bcd3](4923bcd3-opencode-gate-resource-bounds.md) covers detector subprocesses and unbounded Git diff input. This ticket covers persistent and session-lifecycle state retention.

## What probably needs to be done

- Define age and size limits for telemetry and temporary session markers.
- Prune opportunistically with a low-cost bounded operation or a maintenance command.
- Delete OpenCode session state on a reliable session-end event where available, with age-based fallback.
- Document whether telemetry is diagnostic, analytical, or audit data and retain only what that purpose requires.

## Acceptance criteria

- Telemetry cannot exceed a documented age or size budget without pruning.
- Temporary engagement markers expire and are removed deterministically.
- Closed or abandoned OpenCode sessions cannot retain map entries indefinitely.
- Retention tests use bounded fixtures and preserve recent data.

## Sources

- `core/gates/detectors/_hooklib.py:321-329`, `core/gates/detectors/_hooklib.py:359-413`
- `core/gates/detectors/task-workflow-engagement.py:51-57`, `core/gates/detectors/task-workflow-engagement.py:83-91`
- `adapters/opencode/plugins/mainframe-gates.js:261-265`, `adapters/opencode/plugins/mainframe-gates.js:354-395`
- Read-only local state measurement on 2026-07-15
