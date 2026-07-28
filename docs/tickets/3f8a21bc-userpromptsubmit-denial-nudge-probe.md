---
id: 3f8a21bc
title: "Probe UserPromptSubmit additionalContext live, then decide the permission-denial feedback nudge (harness-feedback v2)"
status: open
priority: low
component: hooks
discovered: 2026-06-10
discovered-from: []
tags: ["hooks", "harness-feedback", "verification", "nudge"]
---

# 3f8a21bc: Probe UserPromptSubmit additionalContext live, then decide the permission-denial feedback nudge

## What was observed

harness-feedback v1 (ADR 0075) shipped without the third planned nudge — a reminder after permission denials. `PermissionDenied` hooks have no text-to-agent channel (verified 2026-06-10: installed binary string table shows only `hookSpecificOutput.retry`; official docs agree; hub map `docs/layers/hooks.md` §1.7 agrees). The designed workaround — a `UserPromptSubmit` hook that reads the telemetry DB (`permission_denied` rows for the current `session_id`) and injects a once-per-session `additionalContext` nudge — was cut by the decision-reviewer: a per-prompt python process spawn in EVERY project for a channel of medium confidence.

Channel evidence so far: official docs claim `hookSpecificOutput.additionalContext` is honored for `UserPromptSubmit`; binary strings show `additionalContext` and `initialUserMessage` in its dispatch path. NOT yet probed in a live session.

## Why it is a problem

Permission-denial friction is the highest-value feedback class (auto-mode runs stall on it) and currently has no event-driven nudge — only the skill description covers it semantically. If the channel works and the cost is acceptable, the nudge closes that gap; if not, the gap should be a recorded limitation, not an ambiguity.

## Why it is not a duplicate

- [#40654275](40654275-telemetry-enable-canblock-events.md) — verifying the *empty-output no-op* contract on `UserPromptSubmit` to enable passive telemetry. This ticket verifies the *injection* path (`additionalContext` actually reaching the model) to build an active nudge. Same event, different contract; one live probe session could close both — coordinate when picking either up.

## What probably needs to be done

1. Live probe: register a scratch `UserPromptSubmit` hook emitting `hookSpecificOutput.additionalContext`; confirm in-session that the model sees the text (and measure added per-prompt latency of the python spawn). Source of truth = installed CLI.
2. If channel works and latency is acceptable (<~50ms p95): implement `feedback-nudge-denials.py` — query telemetry DB for `permission_denied` rows of the current session, inject ONCE per session, fail-safe, plus a `feedback_nudge` telemetry row; register in `hooks.json`.
3. If channel fails or cost is too high: record the limitation in ADR 0075 and `docs/layers/hooks.md`, close as wont-fix.
4. Either way, update hub map §1.7 with the probe result (it currently carries the docs+binary claim, unprobed).

## Acceptance criteria

- The `UserPromptSubmit` → `additionalContext` injection is confirmed or refuted by a live session probe, recorded in `docs/layers/hooks.md` §1.7.
- Either `feedback-nudge-denials.py` is live (registered, fail-safe, once-per-session, telemetry row) or ADR 0075 records the wont-fix with the probe evidence.
- No per-prompt hook ships without a measured latency number.

## Sources

- ADR 0075 (`docs/decisions/0075-harness-feedback-channel.md`) — the cut and its rationale.
- `docs/layers/hooks.md` §1.7 — `UserPromptSubmit` row (docs+binary evidence, 2026-06-10).
- decision-reviewer verdict 2026-06-10 (session b1c19a40): objection 1, "ship v1 without nudge (c)".
