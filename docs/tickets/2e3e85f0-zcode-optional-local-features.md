---
id: 2e3e85f0
title: Add ZCode feedback and telemetry only as independent local features
status: open
priority: low
component: zcode-desktop
discovered: 2026-08-05
discovered-from: []
tags: ["zcode", "feedback", "telemetry", "features"]
---

# 2e3e85f0: Add ZCode feedback and telemetry only as independent local features

## What was observed
The ZCode core bundle includes mandatory dormant diagnostics, but it does not yet project the optional MAINFRAME feedback queue or local telemetry feature. Those features are not required for instructions, skills, agents, hooks, secrets, or lifecycle safety.

## Why it is a problem
Adding them inside the base component would make optional state unavoidable and blur the boundary between adapter health diagnostics and activity collection.

## Why it is not a duplicate
Existing telemetry tickets cover detector behavior. This ticket covers ZCode feature packaging, selection, and removal.

## What probably needs to be done
Reuse the existing feature-unit lifecycle after the local ZCode core passes live acceptance. Give each feature its own adapter-local target, preview, selection flag, rollback, and uninstall proof. Do not record prompts, code, secret values, or remote submissions.

## Acceptance criteria
- Feedback and telemetry are absent when only `zcode-desktop` is selected.
- Each feature can be selected and removed independently.
- All state stays under the ZCode adapter root and contains no prompt, code, or credential values.
- A failed optional feature does not block the base adapter.

## Sources
- `adapters/zcode-desktop/build_bundle.py`
- `tools/release_diagnostics.py`
- `docs/decisions/0075-harness-feedback-channel.md`
- `docs/decisions/0076-dev-optin-instrumentation.md`
