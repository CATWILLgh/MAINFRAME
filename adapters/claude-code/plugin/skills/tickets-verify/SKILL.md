---
name: tickets-verify
description: Prepare a goal that independently checks implemented tickets, archives proven fixes, and returns failed work to the correct open queue without repairing it inline.
argument-hint: "[scope]"
disable-model-invocation: true
---

# Verify implemented tickets

Use this command from a fresh session that did not implement the queued work.
Do not start verification in the invocation turn. Return only this copyable
block, with the invocation argument preserved as written:

```text
/goal Follow the loaded tickets-verify workflow. Scope: "$ARGUMENTS"; an empty scope means every eligible ticket in open/needs-verification. Continue one ticket at a time until each eligible implementation has been independently checked and its ticket has either moved unchanged in identity to archive/resolved or returned to ready, needs-scope-review, or needs-decision with precise failed-verification evidence; or stop with an evidenced external blocker that prevents any eligible work from continuing. Before finishing, surface ticket verdicts, reproduced evidence, queue transitions, and completion evidence in the conversation.
```

When that goal starts, first read
[ticket-autonomous-runs.md](../../references/ticket-autonomous-runs.md),
[ticket-format.md](../ticket/ticket-format.md), and the `testing-strategy` skill.

Work only from `open/needs-verification`. A plain-language argument may narrow
the queue by ticket id, path, component, or concern but grants no new authority.
Do not verify an implementation produced earlier in the same session.

For each ticket, distrust both its prose and a green command in isolation.
Inspect the actual implementation and relevant history, reproduce the original
gap or its regression protection, run focused and proportionate broader checks,
and verify the affected business contract, error paths, and cleanup behavior.
Use deterministic interleavings for concurrency claims and the real consumer
or artifact shape when generated output is part of the result.

On success, append concise independent evidence and move the ticket to the
immutable `archive/resolved` path. On failure, do not repair code inline:
append exact evidence and return the same ticket to `ready` for an incomplete or
incorrect implementation, `needs-scope-review` for missed scope, or
`needs-decision` for a newly exposed user-owned choice. A disproved or duplicate
claim goes to `archive/rejected`. Commit only the resulting ticket-state update
as a coherent local recovery point when appropriate; never modify an archived
file afterward.
