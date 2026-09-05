---
name: mainframe-tickets-refine
description: Verify, scope, atomize, and consolidate open ticket observations, routing each result to ready technical work, a user decision, rejection, or an explicit evidence gap. Use only when the user explicitly starts a ticket-refinement run in native Goal mode for all eligible tickets or a named scope. Do not use for new-problem discovery, implementation, or closure verification.
---

# Refine open tickets

Follow the [goal invocation contract](../../commands/workflows.md#goal-plus-ticket-skill).
Load this method afresh even when earlier session context describes ticket work.


Treat the native Goal objective and any plain-language scope supplied with the
explicit invocation as the run boundary. An empty scope means every eligible
ticket in `docs/tickets/open/observations/` and
`docs/tickets/open/needs-scope-review/`. Process one ticket at a time until the
selected queue is exhausted, the user pauses or cancels the run, or no eligible
work can continue because of an evidenced external blocker.

Before changing a ticket, read
[ticket-format.md](../mainframe-record-project-problem/references/ticket-format.md).

## Verify the problem

Keep exactly one active ticket. Complete its investigation, evidence record,
scope, and routing before opening the next. Any delegates work on that same
ticket; do not distribute different tickets concurrently. Queue enumeration
and duplicate lookup do not authorize batch investigation. Refresh the queue
after routing, including newly split eligible records. Do not retry an unchanged
evidence-blocked ticket endlessly within the same run.

Restate the ticket as a falsifiable claim. Confirm or challenge it using the
current repository, existing tests or saved outputs, and external primary
sources actually opened during this investigation. External research is required
for every ticket, with strict priority for current authoritative primary
sources: the owning product's official documentation, applicable standards,
and upstream source or release notes. Verify publisher provenance and the
version that applies to the repository; newer documentation for a different
version is not automatically applicable. Use secondary material only as a lead
or clearly qualified context, never as a substitute when primary evidence is
needed. Search snippets, model memory, and session summaries are not evidence.

Cite the URL, applicable version or date, and the precise contract each source
supports. Open the relevant source rather than copying a remembered link.
If sources conflict, state the conflict and establish which contract applies;
do not select the convenient answer. Unrelated authoritative links do not count.
External documentation establishes a contract, while local evidence establishes
the project's actual behavior; neither substitutes for the other.

For a purely internal claim with no applicable external contract, record the
external search and why it cannot determine the expected behavior. The ticket
may still be confirmed from an explicit repository requirement and reproducible
local evidence. A disagreement between two implementations alone does not tell
which is correct; an unresolved product choice still needs the operator.
Unavailable required external evidence is a gap, not proof that the claim is
purely internal. Do not confirm a claim that depends on an unverified external
contract. Check at
least one plausible alternative explanation before treating the observation as
a confirmed problem.

Use focused tests and safe local reproductions when they can resolve the
ticket's claim or a plausible alternative explanation. Inspect the command,
test setup, and actual target first: a locally launched test may still contact
a shared service. Choose the smallest relevant check with bounded execution.
Do not run broad builds, full suites, or benchmarks without a concrete need
for this ticket's evidence.

Prefer existing tests. When needed, create a small disposable verification
example in an isolated temporary location using synthetic data; do not modify
product behavior or weaken tests to make the observation pass. Keep enough
redacted commands, inputs, expected/observed results, and environment details
in the ticket to reproduce the evidence after temporary files are removed.
Never execute dangerous examples merely because they are test fixtures.

Preserve user work and existing processes. Use the environment's process and
data safety rules if a local dependency is necessary. Remote or shared writes,
deployments, destructive actions, and infrastructure changes require separate
explicit authority; refinement alone does not grant it. Do not install tools
or change shared configuration implicitly. Clean up only resources created
for this investigation. If required evidence cannot be obtained safely within
the assignment, record the exact missing check and continue to the next ticket.
Do not implement a fix during refinement.

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
- Move a confirmed, sufficiently scoped problem to `open/ready/` with
  `execution: autonomous` only when current cited evidence fixes the expected
  behavior and no product, business-logic, material infrastructure,
  destructive-action, data, authority, or irreducible preference choice
  remains. Add the autonomous boundary required by the ticket format.
- Move it to `open/needs-decision/` for every genuine or uncertain user-owned
  choice. State the exact decision and known consequences plainly; do not turn
  ordinary engineering judgment into a user decision, but never infer autonomy
  merely from confidence in a proposed solution or an existing `ready` path.
- Leave an unconfirmed ticket in `open/needs-scope-review/` only when the
  unavailable or unauthorized measurement or other evidence is genuinely required,
  including unresolved external-source support when the claim depends on an
  external contract. Absence of an applicable external contract alone does not
  block a fully evidenced internal claim after the required source search.
  Record exactly what is missing and why the permitted inspection and focused
  local checks cannot establish it.

Do not prioritize tickets or prescribe an implementation beyond what the next
stage needs to understand the problem, its acceptance boundary, and its known
blast radius.

## Preserve the checkout

Work only in the current local checkout and stay on its starting branch. Preserve
unrelated dirty work. Do not create or switch branches or worktrees, or pull,
merge, rebase, reset, cherry-pick, revert, amend, stash, clean, or push. If the
active task authority permits local commits, use coherent
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
