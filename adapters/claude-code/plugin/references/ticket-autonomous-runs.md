# Autonomous ticket runs

These runs belong to the primary session. Process one ticket or one bounded
coverage area at a time; use specialist context or background agents only when
their value exceeds their briefing and verification cost.

## Fixed boundaries

- Work only in the current local checkout and remain on the branch present at
  invocation. Do not create or switch branches or worktrees, and do not pull,
  merge, rebase, reset, cherry-pick, revert, amend, stash, clean, or push.
- Do not touch a test, staging, production, or other external environment
  without separate explicit authority. Repository access does not grant live
  infrastructure authority.
- Preserve unrelated dirty work. Stage and commit only coherent changes owned
  by the current run. Local Conventional Commits are recovery points during a
  long run; they are not permission to push.
- Do not ask the user to resolve technical choices. Route a genuine product,
  business-logic, material infrastructure, destructive-action, or missing-
  authority decision to `needs-decision`, then continue with other eligible
  work.
- Record incidental out-of-scope findings through the ticket skill's
  `record-observation.md`, then resume the run.
- Use current authoritative documentation when a changing external contract
  matters. Use repository evidence for local facts. Do not force both Context7
  and web research when one current primary source settles the claim.

Read the ticket skill's `ticket-format.md` before changing a ticket. Never edit
an archived ticket. A technical blocker ends the goal only when current
evidence shows that no eligible work can continue; surface what blocks the run
and why it could not reasonably have been known at the start.

## Completion evidence

Before the final turn ends, state in plain language:

- the exact queue or scope examined;
- what was processed and where each ticket moved;
- the checks that establish the completion condition;
- any evidenced blocker or remaining user-owned decision.

Keep the report short, but explicit enough for the `/goal` evaluator to judge
the condition from the conversation without reading files or running tools.
