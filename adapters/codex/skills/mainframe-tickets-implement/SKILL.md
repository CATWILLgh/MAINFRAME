---
name: mainframe-tickets-implement
description: Implement technically ready open tickets one at a time, establish focused red evidence where useful, validate each complete fix, commit coherent recovery points, and queue results for independent verification. Use only when the user explicitly starts a ticket-implementation run in native Goal mode for all ready tickets or a named scope. Do not use for ticket discovery, refinement, user-owned decisions, or closure verification.
---

# Implement ready tickets

Treat the native Goal objective and any plain-language scope supplied with the
explicit invocation as the run boundary. An empty scope means every eligible
ticket in `docs/tickets/open/ready/`. Process one ticket at a time until the
selected queue is exhausted or no eligible work can continue because of an
evidenced external blocker.

Before changing a ticket, read
[ticket-format.md](../mainframe-ticket/references/ticket-format.md). Use the
owning engineering skill and its testing boundary when specialized knowledge is
needed. Load
[mainframe-testing-strategy](../mainframe-testing-strategy/SKILL.md) only when
the ticket requires a deliberate cross-cutting decision about test levels,
suite cost, infrastructure, or broad regression coverage.

## Recheck the ticket

Confirm that the ticket remains in `open/ready/`, its evidence still matches the
current repository, and its stated scope covers the meaningful affected paths.
Do not silently expand a ticket whose blast radius is materially incomplete.

- Return it to `open/needs-scope-review/` when affected locations or
  consequences require separate refinement.
- Move it to `open/needs-decision/` when implementation exposes a product,
  business-logic, material infrastructure, destructive-action, or authority
  choice owned by the user.
- Continue with other eligible tickets after routing one away from `ready`.

## Establish red evidence

Before changing behavior, obtain the smallest faithful failing test,
reproduction, measurement, or other observable proof when it can demonstrate
the reported gap. Confirm that it fails for the intended reason, not because of
unrelated setup. Do not create a ceremonial test for documentation-only,
generated, or purely structural work that a deterministic check proves better.

Inspect every command, project script, fixture, setup step, and external
dependency before running it. Use existing local infrastructure only when its
semantics are part of the ticket. Do not touch a remote, shared, staging, or
production environment without separate explicit authority.

## Implement and validate

Implement the complete smallest solution for the confirmed ticket, including
necessary regression coverage and cleanup. Do not leave TODOs, placeholders,
suppressed failures, weakened assertions, skipped tests, or a follow-up shopping
list in place of the requested result.

Run the focused proof first, then the nearest relevant fast suite and any
proportionate broader check needed for the affected business and technical
contracts. Use a real dependency or deployed check only when that boundary is
the risk and the environment is available and authorized. Report only results
actually observed.

Append concise implementation locations, red and green evidence, validation,
and remaining limitations to the ticket. Move the ticket to
`docs/tickets/open/needs-verification/` only after the implementation is
complete and locally validated. Do not independently close work implemented in
this run; closure belongs to a fresh verification run.

## Preserve delivery boundaries

Work only in the current local checkout and stay on its starting branch.
Preserve unrelated dirty work. Do not create or switch branches or worktrees,
or pull, merge, rebase, reset, cherry-pick, revert, amend, stash, clean, or
push. Create a local Conventional Commit after each coherent verified unit when
the active primary-session authority permits it. Stage only the current
ticket's changes.

For a concrete unrelated problem, read
[record-observation.md](../mainframe-ticket/references/record-observation.md),
record only the observation, and return to the active ticket without
investigating or fixing it inline.

## Complete the goal

After processing the selected queue, perform one control pass for eligible
`ready` tickets left within scope. In the final response, state in plain
language:

- the exact queue and scope processed;
- each ticket implemented or rerouted and its resulting path;
- the red evidence, green validation, and local commit for each implementation;
- any limitation or evidenced blocker that prevented further eligible work.
