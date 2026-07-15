---
id: 6223945c
title: Reconcile Antigravity hook output contracts across 2.x
status: open
priority: medium
component: antigravity-hooks
discovered: 2026-07-15
discovered-from: []
tags: ["antigravity", "hooks", "contract", "schema", "compatibility", "permissions"]
---

# 6223945c: Reconcile Antigravity hook output contracts across 2.x

## What was observed

Normal `PreToolUse` deferral, repeated or non-blocking `Stop`, invalid input, and
broad failure paths return `{}`. Current first-party documentation marks
`PreToolUse.decision` and `Stop.decision` as required. It documents
`allow`/`deny`/`ask`/`force_ask` for `PreToolUse`, but `allow` automatically permits
execution rather than neutrally deferring to user-owned permission policy. For
`Stop`, only `continue` is named; any other string permits stopping, but no
canonical stopping literal is defined.

The installed Antigravity 2.2.1 bundle has a different executable contract. Its
embedded `third_party/jetski/hooks_pb/hooks.proto` contract defines no required
result fields, and both decision fields are omittable. Its Go hook caller decodes
stdout with `protojson`, so an empty object is structurally valid in the installed
version. No schema error or hook disablement has been reproduced there.

## Why it is a problem

The adapter currently accepts every Antigravity major version 2 installation, so
the documented contract can drift beyond the tested 2.2.1 behavior. A future host
may reject `{}` and disable a gate even though local tests stay green. Conversely,
changing no-op `PreToolUse` to `{"decision":"allow"}` without a live ordering test
may bypass the user's Antigravity permission policy. `ask` avoids automatic
execution but may add confirmation prompts to every matched safe tool call.

This is medium priority because compatibility debt is confirmed, but a current
runtime failure is not. It becomes high if a supported 2.x release is shown to
reject `{}` or to lose MAINFRAME gate enforcement.

## Why it is not a duplicate

- [#bce23629](bce23629-live-antigravity-plugin-validation.md) covers the full live
  installation smoke. This ticket requires a focused version and permission-policy
  matrix for hook output semantics.
- [#c2f6d19b](c2f6d19b-budget-and-isolate-antigravity-detectors.md) covers how
  detector failures are isolated, not which JSON shape the host receives.

## What probably needs to be done

1. Run a controlled live experiment on the latest supported 2.x release for
   no-op `{}`, `allow`, and `ask` under representative user permission settings.
2. Verify whether `allow` bypasses, precedes, or composes with the native permission
   decision; do not change the bridge until this ordering is proven.
3. Test `Stop` with `{}` and candidate non-`continue` strings, then record the
   accepted stopping response without inventing an undocumented enum.
4. Define an explicit supported-minor policy or version-aware contract if 2.2.1
   and current releases differ in behavior.
5. After the behavior is known, add Tier 1 contract fixtures for every event and
   change only the response branches that are invalid for supported versions.

## Acceptance criteria

- A repeatable matrix records host version, native permission setting, hook output,
  whether the tool ran, whether the user was prompted, and any protocol error.
- No no-op response bypasses user-owned Antigravity permission settings.
- Every supported version has positive, no-op, malformed-input, and detector-failure
  output contract tests derived from observed host behavior.
- Stop behavior is confirmed without accidental continuation or a guessed literal.
- PostToolUse emits exactly the documented empty object.
- The generated hook command always prints one valid JSON document and no noise.

## Sources

- `adapters/antigravity-2/gates/mainframe_hook.py:129-143` — shared no-op and
  exception behavior.
- `adapters/antigravity-2/gates/mainframe_hook.py:167-195` — `PreToolUse`
  response selection.
- `adapters/antigravity-2/gates/mainframe_hook.py:256-285` — `Stop` responses.
- `adapters/antigravity-2/build_antigravity.py:303-321` — major-version-only
  native validation.
- `/Applications/Antigravity.app/Contents/Info.plist` — installed version 2.2.1.
- `/Applications/Antigravity.app/Contents/Resources/bin/language_server` — embedded
  `hooks.proto` descriptor and `jsonhook.(*Caller).CallHook` implementation.
- [Official Antigravity hooks documentation](https://antigravity.google/docs/hooks)
  — current public event contracts.
- [First-party raw hooks documentation](https://antigravity.google/assets/docs/antigravity-2-0/hooks.md)
  — source form used for contract verification on 2026-07-15.
