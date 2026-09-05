# Resolve one ticket with the user

Use this route only when the explicit `mainframe-init` invocation names one
four-character ticket id. It handles that ticket from
`docs/tickets/open/needs-decision/` within the assigned task. Do not select a second
ticket, consume an autonomous queue, or treat a missing id as permission to
choose one. Read
[ticket-format.md](../../mainframe-record-project-problem/references/ticket-format.md) before
changing the ticket.

## Establish the real decision

Find the single open `needs-decision` ticket with the exact id. Read its full
history and inspect the current affected repository paths. Verify any changing
external contract through current owning documentation. Finish this bounded
preparation before asking the user so the first question already contains the
relevant facts, viable choices, practical consequences, and a recommendation
in plain language.

If you cannot address the operator, return the prepared decision to your caller.
Ask only for a product or business-logic choice, a material infrastructure
choice, missing authority, or an irreducible preference. Resolve engineering
and architecture choices independently. Ask one decision-changing question at
a time; do not make the user approve intermediate research or routing.

If the ticket is not actually ready for a user decision, move it to
`open/needs-scope-review/` with the missing evidence. If the issue is disproved,
superseded, or a duplicate, move it to `archive/rejected/` with the evidence and
finish without implementation.

## Prepare implementation

After the decision is settled:

1. Record the decision and its reason in the ticket.
2. Agree a concise definition of done made of observable product behavior and
   material constraints. Use decision and readiness review when they materially
   improve confidence, with a separate reviewer when independence is needed.
3. Obtain focused red evidence before implementation when it can demonstrate
   the gap. Use the smallest faithful test, reproduction, measurement, or
   structural check that proves the affected contract; do not create a
   ceremonial test for a structural-only change. When
   `mainframe-testing-strategy` is available, it may refine a deliberate
   cross-cutting testing decision.
4. Append the agreed definition of done and red evidence, set
   `execution: user-approved`, then move the same ticket to `open/ready/`.

When the request is preparation-only, return one copyable objective using
`{{COMMAND_BINDING}}`. When implementation is already authorized, continue within
that authority. The goal objective names the ticket, the
agreed definition of done, the prepared red evidence, and the required final
transition:

```text
Implement only ticket <id>, marked execution: user-approved, against the agreed definition of done. Continue until every acceptance condition is demonstrated, the prepared red evidence is green, proportionate regression checks pass, the same ticket contains concise implementation evidence and is moved to docs/tickets/open/needs-verification/, or stop when the user asks to pause or cancel, with a newly evidenced user-owned decision, or with an external blocker that makes completion unreachable. Before finishing, report the result, checks, ticket transition, and any blocker in plain language.
```

The implementation stays in the current checkout and starting branch. It may
create local Conventional Commits as coherent recovery points. It must not
switch or create branches or worktrees, alter history, push, or mutate an
external environment without separate explicit authority. Independent closure
belongs to a later fresh `mainframe-tickets-verify` task.
