---
id: 40654275
title: Enable telemetry on the 3 gated can-block events after verifying empty-output contract
status: open
priority: low
component: hooks
discovered: 2026-06-04
discovered-from: ["#faa110d8"]
tags: ["hooks", "telemetry", "verification"]
---

# 40654275: Enable telemetry on the 3 gated can-block events after verifying empty-output contract

## What was observed

ADR 0073 registered `telemetry.py` only on events where "empty stdout + exit 0 = no-op" is either proven in-repo (`SessionStart`/`PreToolUse`/`PostToolUse`) or the event cannot block (`PermissionDenied`/`SubagentStart`/`SessionEnd`). Three **can-block / inject-path** events were gated out because their empty-output contract was not verified live (Context7 was erroring at the time, and the hooks were not live in-session to test):

- `UserPromptSubmit` (a hook here can erase the prompt) — metric: turns per task.
- `SubagentStop` (can block parent continuation) — metric: sub-agent duration.
- `PreCompact` (can block compaction) — metric: compaction frequency.

`telemetry.py` already contains the handler branches for these; only the `hooks.json` registrations were withheld.

## Why it is a problem

Three low-value-but-real Bucket-1 metrics are uncollected. More importantly, the decision to gate was made on caution, not evidence — it should be closed with a real verification rather than left ambiguous.

## Why it is not a duplicate

- [#e5308bd1](e5308bd1-opencode-telemetry-source-tag.md) added source-aware
  telemetry and OpenCode dispatch. This ticket is limited to three withheld
  Claude Code lifecycle registrations and their empty-output/no-block
  contract.
- [#faa110d8](faa110d8-telemetry-detector-incident-wiring.md) owns
  `incident` events emitted by security and quality detectors. It does not
  cover `UserPromptSubmit`, `SubagentStop`, or `PreCompact` lifecycle rows.

## What probably needs to be done

- Verify the contract: a hook on `UserPromptSubmit` / `SubagentStop` / `PreCompact` that exits 0 with empty stdout is a no-op (no context injection, no block, no warning, no added latency). Source of truth = the installed CLI (use the `claude-code-research` pattern: `claude-code-guide` + docs).
- Once confirmed: re-add the three registrations to `plugin-dist/hooks/hooks.json` (matcher `*`, `telemetry.py`).
- Validate on a real session: the telemetry DB gains `turn` / `subagent_stop` / `compaction` rows and the session is visibly unaffected.

## Acceptance criteria

- Documented confirmation (doc quote or CLI inspection) that empty-output is inert for these events.
- Registrations re-added; DB shows the rows; no prompt-path / turn regression observed.

## Sources

- ADR 0073 — `docs/decisions/0073-telemetry-layer.md` ("3 can-block события отложены").
- `docs/layers/hooks.md` §1.7 (decision-control per event).
