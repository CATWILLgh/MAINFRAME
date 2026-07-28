---
id: d245b10d
title: "Measure advisor calls via transcript parse (tool hooks structurally cannot)"
status: open
priority: medium
component: hooks
discovered: 2026-06-08
discovered-from: []
tags: ["telemetry", "advisor", "measurement-integrity"]
---

# d245b10d: Measure advisor calls via transcript parse (tool hooks structurally cannot)

## What was observed

The `advisor_call` telemetry branch produced **0 rows across 68 sessions** despite real advisor use. `claude-code-guide` (installed CLI 2.1.165 + Anthropic advisor-tool docs) confirmed the root cause: **advisor is a `server_tool_use` block, resolved server-side inside the `/v1/messages` request and returned as an `advisor_tool_result` block — it is never executed by the Claude Code client.** `PreToolUse` / `PostToolUse` fire only on client-side tool execution, so advisor is **structurally invisible** to the tool-use hook pipeline (no `tool_name`, no hook event, at any name).

The dead `if tool == "advisor"` branch in `telemetry.py` and the `advisor` token in the `PreToolUse` matcher were removed (this resolves the dead-code half).

## Why it is a problem

The advisor-per-cycle metric in the ADR 0073 decision-linkage table ("`advisor_call` per cycle below the ≥2/cycle target → the advisor discipline isn't followed → investigate") is now **unmeasured**. The advisor discipline is high-value (umbrella CLAUDE.md mandates advisor before substantial work, when stuck, and before declare-done), so the metric is worth keeping — just via a mechanism that can actually see advisor.

## Why it is not a duplicate

- [faa110d8](faa110d8-telemetry-detector-incident-wiring.md) — detector `incident` wiring.
- [40654275](40654275-telemetry-enable-canblock-events.md) — enabling can-block events.
- [a7c5a653](a7c5a653-telemetry-ticket-writecount-skill-name-normalization.md) — ticket/skill payload semantics.
This ticket is specifically the **advisor-measurement mechanism** — a distinct gap.

## What probably needs to be done

- Measure advisor invocations by **parsing the session transcript** at `Stop` or `SessionEnd` (both carry `transcript_path` in the hook payload): count `server_tool_use` blocks with `name == "advisor"` (or `advisor_tool_result` blocks) per turn / cycle, and log an aggregate (`advisor_call` count, or `advisor_per_cycle`).
- **Caution — `Stop` is the sensitive gate surface.** If hooking `Stop`, keep the telemetry read fully isolated and positioned *after* any gate's decision path (same discipline as the detector-incident wiring in faa110d8); verify the gate's decision path stays byte-identical. `SessionEnd` is lower-risk (cleanup-only) and may be the better host.
- Privacy: count only — never log transcript text, only the integer count.

## Acceptance criteria

- Advisor invocations measured via transcript parse; rows appear for sessions where advisor was used; the ≥2/cycle metric is computable.
- `tools/test_telemetry.py` privacy assertion still holds (no transcript text / banned keys logged).
- If hosted on `Stop`: each existing Stop gate's decision path verified byte-identical before/after.

## Sources

- `claude-code-guide` finding (advisor = `server_tool_use`, server-side, not client-executed; CLI 2.1.165).
- `plugin-dist/hooks/scripts/telemetry.py` (the removed branch); `plugin-dist/hooks/hooks.json` (matcher).
- ADR 0073 §4 (probe-to-confirm) + decision-linkage table; memory `advisor-tool-mechanics`.
