---
id: d38d93a4
title: Add bounded redacted diagnostics for Antigravity hook failures
status: open
priority: medium
component: antigravity-hooks
discovered: 2026-07-15
discovered-from: []
tags: ["antigravity", "observability", "hooks", "diagnostics", "privacy"]
---

# d38d93a4: Add bounded redacted diagnostics for Antigravity hook failures

## What was observed

`Bridge.handle()` swallows every exception and returns `{}`. Detector and memory
subprocess standard error is discarded, and parse, timeout, packaging, and
permission failures produce the same observable result as an intentional no-op.
The current infrastructure-failure test asserts only that the hook stays silent.

## Why it is a problem

A globally installed gate or memory adapter can remain partially inactive with
no way to distinguish a broken helper from normal deferral. Silent fail-open is
appropriate for hook stdout, but not as the only diagnostic channel. Logging raw
payloads would create a separate credential and privacy risk.

## Why it is not a duplicate

- [#c2f6d19b](c2f6d19b-budget-and-isolate-antigravity-detectors.md) fixes runtime
  control flow; this ticket makes remaining failures diagnosable.
- [#bce23629](bce23629-live-antigravity-plugin-validation.md) verifies activation
  once; it does not provide ongoing operational visibility.

## What probably needs to be done

1. Define an adapter-owned diagnostic location under Antigravity application data.
2. Record timestamp, event, component, error class, and bounded status only.
3. Never record commands, tool arguments, memory content, transcript content,
   credentials, or full sensitive paths.
4. Bound file size/count and tolerate logging failure without affecting stdout.
5. Keep exactly one schema-valid JSON document on hook stdout.

## Acceptance criteria

- Tests force spawn failure, timeout, malformed JSON, oversized output, missing
  helper, permission denial, and logging failure.
- Each supported failure writes a bounded redacted diagnostic with event and
  component identity.
- A secret-shaped fixture and command text never appear in the diagnostic file.
- Rotation or pruning keeps diagnostics within named limits.
- Successful and intentional no-op events do not create misleading error entries.

## Sources

- `adapters/antigravity-2/gates/mainframe_hook.py:129-143`
- `adapters/antigravity-2/gates/mainframe_hook.py:301-352`
- `tools/test_antigravity_hook.py:197-204`
- `adapters/antigravity-2/gates/mainframe_state.py:13-42`
