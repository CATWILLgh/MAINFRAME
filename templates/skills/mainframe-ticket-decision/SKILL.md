---
name: mainframe-ticket-decision
description: Investigate one named ticket requiring an operator decision, present grounded options, record the agreement, and prepare a separate implementation or resumed-verification goal. Use for ticket decision preparation, not session initialization, queue processing, or implementation.
---

# Resolve one ticket with the user

Use this route only when the explicit `mainframe-ticket-decision` invocation names one
exact ticket id (including a preserved legacy id). It handles that ticket from
`docs/tickets/open/needs-decision/` within the assigned task. Do not select a second
ticket, consume an autonomous queue, or treat a missing id as permission to
choose one. Read
[ticket-format.md](../mainframe-record-project-problem/references/ticket-format.md) before
changing the ticket.

Run this as a conversation before the next execution goal. It is not session
initialization and does not consume the find/refine/implement/verify queues.
If the id is missing or ambiguous, ask for the exact ticket before mutation.
A delegate may prepare evidence for its caller, but cannot invent operator consent.

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

## Return blocked verification to its own stage

Establish from the ticket history whether it needs implementation or only a
blocked verification check. If implementation is already complete and the
operator resolves the verification blocker, record the decision and its exact
authority, preserve the execution route and existing evidence, and return the
ticket to `open/needs-verification/`. Do not send it to implementation, demand
new red evidence, or mark it resolved merely because access was granted.

Return a copyable objective for a separate fresh `mainframe-tickets-verify`
task scoped to this ticket. Include its absolute path, the original acceptance
boundary, the outstanding checks, and the agreed way to perform them. Check
remaining prerequisites before presenting the objective as executable; if a
required operator step is still pending, leave the ticket in `needs-decision`.
The operator submits the goal separately. Do not perform closure in this
conversation. If the decision actually changes product behavior or exposes an
incomplete implementation, use the implementation route below, or return to
scope review when the revised scope lacks evidence.

## Prepare implementation when code or behavior must change

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

Return one ready-to-copy objective using the documented native goal invocation
resolved through `{{COMMAND_BINDING}}`. Include the absolute repository path,
exact ticket id, agreed decision, scope and authority, definition of done,
prepared evidence, validation requirements, and final transition. Resolve the
example below into concrete instructions usable without this conversation.
Do not start the implementation goal or implement the fix in this workflow;
the operator copies and submits the objective separately. If native goals are
unavailable, report the limitation rather than inventing a command.

The implementation objective follows this boundary:

```text
Implement only ticket <id>, marked execution: user-approved, against the agreed definition of done. Continue until every acceptance condition is demonstrated, the prepared red evidence is green, proportionate regression checks pass, the same ticket contains concise implementation evidence and is moved to docs/tickets/open/needs-verification/, or stop when the user asks to pause or cancel, with a newly evidenced user-owned decision, or with an external blocker that makes completion unreachable. Before finishing, report the result, checks, ticket transition, and any blocker in plain language.
```

Both preparation and the later implementation stay in the assigned checkout
and starting branch, preserving unrelated work. Local Conventional Commits
may be used as recovery points only when authorized. It must not
switch or create branches or worktrees, alter history, push, or mutate an
external environment without separate explicit authority. Independent closure
belongs to a later fresh `mainframe-tickets-verify` task.
