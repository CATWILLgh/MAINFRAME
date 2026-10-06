# Unsupported capability

## Use when

Current evidence establishes that the installed product and surface cannot
represent a required MAINFRAME semantic, under the
[verification threshold](../verification.md#unsupported-is-evidence-not-failure-concealment).

## Desired result

A precise, honest `delivery: unsupported` state with no `verification` field
that does not fabricate parity and does not prevent independent components from
being installed.

## Inspect

Name the required semantic and the missing native property: discovery,
user-only invocation, event timing, blocking, advisory delivery, continuation,
attribution, role routing, permission enforcement, or another exact boundary.

## Adapt

Use a narrower representation as full delivery only when it still satisfies the
complete canonical component. For hooks, follow the
[native placement search](../components/hooks.md#keep-native-integration-thin):
evaluate safe post-action, completion, and other relevant lifecycle bindings,
and install useful partial effects even when full parity is impossible.
Report them separately; delivery remains `unsupported` when a required rule
is absent. Omit a binding only when the available alternatives would be unsafe,
misleading, wrongly attributed, or noisier than their useful signal.

## Verify

Apply the evidence threshold from [verification.md](../verification.md).
Distinguish an actual capability limit from a failed setup, unavailable probe,
untested surface, or deprecation. Recheck after relevant source, adapter,
configuration, or product changes.

## Record

Set delivery to `unsupported`, omit `verification`, and put the exact missing
semantic in `reason`. State the product version, surface, concise evidence, and
any retained partial implementation in the final report. Missing proof is not a
limitation: keep verification `pending` with the missing step in `next_action`.
Continue with independent inventory entries.

## Never do

Never claim a prompt enforces a guard, an ordinary prompt file is a subagent,
an advisory is a required block, or file presence proves native discovery.
