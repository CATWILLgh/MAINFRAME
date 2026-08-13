---
name: tickets-implement
description: Prepare a goal that implements technically ready tickets one at a time, obtains red evidence where useful, validates each result, and queues it for independent verification.
argument-hint: "[scope]"
disable-model-invocation: true
---

# Implement ready tickets

Do not start implementation in the invocation turn. Return only this copyable
block, with the invocation argument preserved as written:

```text
/goal Follow the loaded tickets-implement workflow. Scope: "$ARGUMENTS"; an empty scope means every eligible ticket in open/ready. Continue one ticket at a time until each eligible ticket has either a complete locally validated implementation in open/needs-verification or has been returned to needs-scope-review or needs-decision with the newly discovered boundary; or stop with an evidenced external blocker that prevents any eligible work from continuing. Before finishing, surface ticket outcomes, red and green evidence, validation, commits, and completion evidence in the conversation.
```

When that goal starts, first read
[ticket-autonomous-runs.md](../../references/ticket-autonomous-runs.md),
[ticket-format.md](../ticket/ticket-format.md), and the `testing-strategy` skill.

Work only from `open/ready`. A plain-language argument may narrow the queue by
ticket id, path, component, or concern but grants no new authority. For each
ticket:

1. Recheck that its evidence and scope still match the current repository.
2. Obtain a focused red test, reproduction, measurement, or other observable
   proof before changing behavior when it can demonstrate the gap. Do not add a
   ceremonial test for a purely structural change.
3. Implement the complete smallest solution, including necessary regression
   coverage and cleanup. Do not leave TODOs, placeholders, suppressions, or a
   partial shopping list in code.
4. Run focused checks first, then the proportionate broader validation needed
   for the affected business and technical contracts. Append concise evidence
   and changed locations to the ticket and move it to `needs-verification`.
5. Create a local Conventional Commit for a coherent verified unit during a
   long run, without staging unrelated work.

If implementation exposes missing blast radius, return the ticket to
`needs-scope-review`. If it exposes a real user-owned choice, move it to
`needs-decision` and continue with other eligible tickets. Record unrelated
problems as observations. Do not independently close work implemented earlier
in this same session; closure belongs to a fresh verification run.
