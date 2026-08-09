# Complex-task workflow

Load this file only when the task needs a formal definition of done or is known
to be complex. The preparation is part of the work: do not ask the user to keep
saying “continue” while facts available to the agent remain unchecked.

## Prepare the decision

1. Establish the real dependency chain and verify drift-prone claims against
   current authoritative sources. Research is complete when the important
   assumptions, constraints, alternatives, and path to verification are known;
   do not substitute fixed counts of files, searches, or agents for readiness.
2. Synthesize a neutral decision package: facts, constraints, viable options,
   recommendation, load-bearing assumptions, draft definition of done, and a
   design for the red evidence.
3. Have `decision-reviewer` challenge the proposed decision. Reconcile each
   grounded objection against the repository and sources.
4. Run an independent Codex review after the decision review. Read
   [codex-exec.md](codex-exec.md) for the adapter-specific invocation. Repeat
   only while a new grounded blind spot appears, with no more than three review
   passes.
5. Run the available advisor checkpoint last. Present the user with the checked
   recommendation, remaining product or infrastructure choices, and the draft
   definition of done.

## Agree and launch

- Agree the observable definition of done before implementation.
- After agreement, create and run the smallest real test or other red evidence
  that proves the current gap. Agreement authorizes this preparatory evidence;
  it does not authorize implementation.
- If the evidence disproves the premise, return with the result instead of
  manufacturing a task.
- Prepare a copyable `/goal` command only after the definition of done and red
  evidence are sound. Do not activate it. The user's message containing `/goal`
  is the formal start of autonomous implementation.

## Execute

Work to the agreed goal autonomously. Resolve engineering and architecture
choices without reporting internal routing. If an apparently simple task turns
out to be materially harder, investigate before returning to the user. Continue
when the suspected blocker is false. Return only for a proven product choice,
infrastructure choice, authority boundary, or external condition that changes
the goal or makes it unreachable.

Do not fix an out-of-scope finding inline. Use `surface-ticket` only to find a
similar ticket, create a minimal `needs-refinement` observation, or append new
observations, then return to the goal. A finding that blocks the current
definition of done is in scope and must be investigated.

Create local recovery commits after coherent verified units. Never push or
change branches without the user's explicit instruction.

## Accept the result

Run the tests and checks that prove the definition of done, then run the final
advisor checkpoint against the actual changes and evidence. If its finding
changes the result, repeat the affected verification and advisor review.

A goal ends only when either:

- every acceptance condition is proven; or
- continuing is proven impossible without changing the agreed product,
  infrastructure, authority, or an unavailable external condition.

For the second outcome, report the blocker, evidence, alternatives checked, why
preparation did not reveal it, and whether preparation itself failed. A first
failed attempt or unresolved technical uncertainty is not a blocker. Do not
repeat an unchanged attempt without a new hypothesis or new evidence.

An additional Codex review after the final advisor is reserved for exceptional
cost of error: irreversible data, money, security, broad production impact, or
architecture that is difficult to reverse.
