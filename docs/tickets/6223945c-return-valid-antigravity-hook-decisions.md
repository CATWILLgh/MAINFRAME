---
id: 6223945c
title: Return schema-valid output for every Antigravity hook event
status: open
priority: high
component: antigravity-hooks
discovered: 2026-07-15
discovered-from: []
tags: ["antigravity", "hooks", "contract", "schema"]
---

# 6223945c: Return schema-valid output for every Antigravity hook event

## What was observed

Normal PreToolUse deferral and broad failure paths return `{}`. The current unit
test explicitly expects `{}` when a detector emits only advisory context. The
official Antigravity schema marks `PreToolUse.decision` as required and limits it
to `allow`, `deny`, `ask`, or `force_ask`. The Stop schema likewise declares a
required decision field, while no-op Stop paths also return `{}`.

The local bridge tests call Python methods directly; they do not validate output
against the native per-event schema or prove that Antigravity 2.2.1 accepts an
undocumented empty deferral.

## Why it is a problem

Routine safe tool calls or stops can produce protocol errors, disable a hook, or
behave differently after a host update even though unit tests remain green.
Because the empty response is used as the general fail-open shape, the mismatch
affects both normal operation and infrastructure failures.

## Why it is not a duplicate

- [#bce23629](bce23629-live-antigravity-plugin-validation.md) is the live smoke
  test; this ticket corrects the static event-output contract first.
- [#c2f6d19b](c2f6d19b-budget-and-isolate-antigravity-detectors.md) covers how
  detector failures are isolated, not which JSON shape the host receives.

## What probably needs to be done

1. Define a valid fail-open response for each supported event.
2. Return explicit `allow` for PreToolUse when MAINFRAME has no stronger verdict.
3. Verify the documented non-continuing Stop response rather than assuming `{}`.
4. Validate PreInvocation, PostInvocation, and PostToolUse output shapes as well.
5. Add schema fixtures derived from the official current documentation and a
   live 2.2.1 confirmation after installation approval.

## Acceptance criteria

- Every supported event has positive, no-op, and failure-output contract tests.
- PreToolUse never emits JSON without a valid `decision`.
- Stop behavior is confirmed both against the published schema and in a live
  desktop session, without accidental continuation.
- PostToolUse emits exactly the documented empty object.
- The generated hook command always prints one valid JSON document and no noise.

## Sources

- `adapters/antigravity-2/gates/mainframe_hook.py:129-143`
- `adapters/antigravity-2/gates/mainframe_hook.py:182-195`
- `tools/test_antigravity_hook.py:140-151`
- <https://antigravity.google/docs/hooks>
