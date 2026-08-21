---
name: mainframe-tickets-verify
description: Independently verify implemented tickets, archive proven fixes, and return failed work to the correct open queue without repairing it inline. Use only when the user explicitly starts a ticket-verification run in native Goal mode from a task that did not implement the queued work. Do not use for discovery, refinement, implementation, or product acceptance.
---

# Verify implemented tickets

Treat the native Goal objective and any plain-language scope supplied with the
explicit invocation as the run boundary. An empty scope means every eligible
ticket in `docs/tickets/open/needs-verification/`. Process one ticket at a time
until the selected queue is exhausted, the user pauses or cancels the run, or
no eligible work can continue because of an evidenced external blocker.

Do not continue if this task implemented any selected ticket. Independent
verification must start in a fresh task with no ownership of the implementation.
Before checking a ticket, read
[ticket-format.md](../mainframe-ticket/references/ticket-format.md) and
[mainframe-testing-strategy](../mainframe-testing-strategy/SKILL.md).

## Reconstruct the claim

Confirm that the ticket remains in `open/needs-verification/`, then inspect its
full recorded history, the actual implementation, relevant repository history,
and the current affected paths. Treat the ticket prose, implementation notes,
and prior green commands as leads rather than proof.

State the original observable problem, the claimed correction, and the
business or technical contract that would distinguish success from a plausible
false positive. Inspect every command, project script, fixture, setup step, and
external dependency before running it. Do not touch a remote, shared, staging,
or production environment without separate explicit authority.

## Obtain independent evidence

Reproduce the original gap through its regression protection or the smallest
faithful current observation. Run focused checks and proportionate broader
checks that can expose regressions in the affected contract, meaningful error
paths, and cleanup behavior. Use deterministic interleavings for concurrency
claims. When generated output, serialization, installation, or another
consumer-facing artifact is part of the result, inspect the real produced shape
or consumer boundary rather than only its source.

Use a real dependency or deployed check only when that boundary is the risk and
the environment is available and authorized. Never convert an unavailable
environment, a passing mock, a coverage percentage, or an unrelated green suite
into evidence for a claim it cannot prove. Report only observations made in
this verification task.

## Record the verdict

Do not repair implementation code or tests inline during this run. Preserve the
ticket id and its accumulated history, append concise independent evidence, and
make exactly one evidence-backed transition:

- move a proven fix to immutable `docs/tickets/archive/resolved/`;
- return an incomplete or incorrect implementation to `open/ready/` while
  preserving its existing `execution` route;
- return work with a materially missed blast radius to
  `open/needs-scope-review/`;
- route a newly exposed product, business-logic, material infrastructure,
  destructive-action, or authority choice to `open/needs-decision/`;
- move a disproved, superseded, or duplicate claim to immutable
  `docs/tickets/archive/rejected/`.

Never edit, reopen, rename, or move an archived ticket. A later occurrence is a
new ticket. If verification itself reveals a separate unrelated problem, read
[record-observation.md](../mainframe-ticket/references/record-observation.md),
record only the observation, and return to the selected ticket.

## Preserve delivery boundaries

Work only in the current local checkout and stay on its starting branch.
Preserve unrelated dirty work. Do not create or switch branches or worktrees,
or pull, merge, rebase, reset, cherry-pick, revert, amend, stash, clean, or
push. Commit only the coherent ticket evidence and state transition as a local
Conventional Commit when the active primary-session authority permits it.

## Complete the goal

After processing the selected queue, perform one control pass for eligible
`needs-verification` tickets left within scope. In the final response, state in
plain language:

- the exact queue and scope processed;
- each ticket's verdict and resulting path;
- the independently reproduced evidence and local commit;
- any limitation or evidenced blocker that prevented a reliable verdict.
