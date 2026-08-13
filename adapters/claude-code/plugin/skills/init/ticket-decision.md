# Resolve one ticket with the user

Use this route only for `init ticket <four-character-id>`. It handles one ticket
from `docs/tickets/open/needs-decision/` in the primary session. Do not select a
second ticket, consume the autonomous queue, or treat a missing id as permission
to choose one. Read
[ticket-format.md](../ticket/ticket-format.md) before changing the ticket.

## Establish the real decision

Find the single open `needs-decision` ticket with the exact id. Read its history
and inspect the current repository locations and any changing authoritative
contract needed to validate the prepared decision boundary. Do this before
asking the user so the first question already includes the relevant facts,
viable options, consequences, and a recommendation in plain language.

Ask only for a product or business-logic choice, a material infrastructure
choice, missing authority, or irreducible preference. Resolve engineering and
architecture choices independently. Ask one decision-changing question at a
time and do not make the user approve intermediate research or routing.

If the ticket is not actually ready for a user decision, move it back to
`needs-scope-review` with the missing evidence instead of improvising options.
If the issue is disproved or duplicated, move it to `archive/rejected` with the
evidence and finish without implementation.

## Prepare implementation

After the decision is settled:

1. Record the decision and its reason in the ticket.
2. Agree a concise definition of done made of observable product behavior and
   material constraints. For a complex or high-stakes change, read
   [workflow.md](workflow.md) and complete its architecture and review route
   before proposing the final definition of done.
3. Read the `testing-strategy` skill and obtain focused red evidence before
   implementation when it can demonstrate the gap. The evidence may be a test,
   reproduction, measurement, or another observable check; do not create a
   ceremonial test for a purely structural change.
4. Append the agreed definition of done and red evidence to the ticket, then
   move the same ticket to `open/ready/`.

Do not start implementation before the user sends the goal. Return one
copyable block whose condition names the ticket, the agreed definition of done,
the prepared red evidence, and the required final move to
`open/needs-verification/`:

```text
/goal Implement ticket <id> against the agreed definition of done. Continue until every acceptance condition is demonstrated, the prepared red evidence is green, proportionate regression checks pass, the same ticket contains concise implementation evidence and is moved to open/needs-verification, or stop with a newly evidenced user-owned decision or external blocker that makes completion unreachable. Before finishing, surface the result, checks, ticket transition, and any blocker in the conversation.
```

The implementation remains in the current checkout and branch. It may create a
local Conventional Commit as a recovery point, but must not switch or create a
branch or worktree, alter history, push, or touch an external environment
without separate explicit authority. Independent closure belongs to a later
fresh `tickets-verify` session.
