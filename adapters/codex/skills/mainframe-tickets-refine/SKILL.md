---
name: mainframe-tickets-refine
description: Verify, scope, atomize, and consolidate open ticket observations, routing each result to ready technical work, a user decision, rejection, or an explicit evidence gap. Use only when the user explicitly starts a ticket-refinement run in native Goal mode for all eligible tickets or a named scope. Do not use for new-problem discovery, implementation, or closure verification.
---

# Refine open tickets

Treat the native Goal objective and any plain-language scope supplied with the
explicit invocation as the run boundary. An empty scope means every eligible
ticket in `docs/tickets/open/observations/` and
`docs/tickets/open/needs-scope-review/`. Process one ticket at a time until the
selected queue is exhausted or no eligible work can continue because of an
evidenced external blocker.

Before changing a ticket, read
[ticket-format.md](../mainframe-ticket/references/ticket-format.md).

## Verify the problem

Restate the ticket as a falsifiable claim. Confirm or challenge it using the
current repository, existing tests or saved outputs, and current owning
documentation when the claim depends on a changing external contract. Check at
least one plausible alternative explanation before treating the observation as
a confirmed problem.

Do not run project code, tests, builds, linters, servers, containers, migrations,
benchmarks, or external environments. Do not create verification code and do
not implement a fix. If confirmation requires a new measurement and no existing
contract supplies the boundary, preserve the exact evidence gap instead of
inventing certainty. Continue with other eligible tickets.

## Establish scope and identity

Find the affected locations and meaningful consequences far enough to establish
the known blast radius. Separate independently fixable problems into separate
tickets with new ids while preserving the original observation, history, and
links. Keep one problem per ticket.

Search the open queue for semantic duplicates, not merely matching words. Keep
the clearest ticket as the canonical open record and append only material
evidence from duplicates. Move confirmed duplicates to `archive/rejected/` with
a link to the canonical ticket and a concise reason. Never edit an archived
ticket.

## Route the result

- Move a disproved, superseded, or duplicated ticket to `archive/rejected/`.
- Move a confirmed, sufficiently scoped technical problem to `open/ready/` when
  no new user choice is needed.
- Move it to `open/needs-decision/` only for a product, business-logic, material
  infrastructure, destructive-action, or authority choice. State the exact
  decision and the known consequences plainly; do not turn ordinary engineering
  judgment into a user decision.
- Leave an unconfirmed ticket in `open/needs-scope-review/` only when the
  forbidden new measurement or unavailable evidence is genuinely required.
  Record exactly what is missing and why inspection alone cannot establish it.

Do not prioritize tickets or prescribe an implementation beyond what the next
stage needs to understand the problem, its acceptance boundary, and its known
blast radius.

## Preserve the checkout

Work only in the current local checkout and stay on its starting branch. Preserve
unrelated dirty work. Do not create or switch branches or worktrees, or pull,
merge, rebase, reset, cherry-pick, revert, amend, stash, clean, or push. If the
active primary-session authority permits local commits, use coherent
Conventional Commits only as recovery points for ticket records changed by this
run.

## Complete the goal

After the selected queue has been processed, perform one control pass for
unhandled eligible tickets and duplicate canonical records. In the final
response, state in plain language:

- the exact queue and scope checked;
- which tickets were split, consolidated, rejected, made ready, or routed to a
  user decision;
- any ticket retained for a specific missing measurement or unavailable fact;
- any evidenced blocker that prevented further eligible work.
