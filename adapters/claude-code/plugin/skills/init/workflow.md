# Formal-task workflow

Load this file only when the task needs a formal definition of done or is known
to be complex. Check available facts before asking the user to continue.

## Choose the route

A formal DoD alone does not make a task complex. After enough reconnaissance to
establish scope, choose one route:

- **Bounded formal:** the change is local, reversible, low-risk, has no material
  architecture or infrastructure choice, and has a direct proof. The DoD only
  removes ambiguity about the result.
- **Complex:** the task has material design branches, broad or uncertain blast
  radius, high cost of error, irreversible effects, or load-bearing unknowns. A
  task known to be complex starts here. When in doubt, use this route.

If bounded reconnaissance reveals material complexity, establish the relevant
facts and switch routes before asking the user to agree the DoD.

### Bounded formal route

1. Verify the facts needed to define the observable result and its boundaries.
2. Prepare a concise recommendation, draft DoD, and red-evidence design.
3. Present them without invoking `mainframe-decision-reviewer`, Codex, or
   `advisor` as ceremony.

### Complex route

1. Establish the dependency chain, assumptions, constraints, alternatives, and
   path to verification. Verify drift-prone claims against current authorities.
2. Synthesize the facts, viable options, recommendation, load-bearing
   assumptions, draft DoD, and red-evidence design.
3. Have `mainframe-decision-reviewer` challenge the decision and reconcile each
   grounded objection against the repository and sources.
4. Run an independent Codex review using [codex-exec.md](codex-exec.md).
5. Invoke the built-in zero-argument `advisor` last. Reconcile its findings,
   then present the checked recommendation, choices, and draft DoD.

These checkpoints are required for the complex route. If one is unavailable,
report the missing capability before agreement; do not silently replace it.

## Agree and launch

- Agree the observable DoD before implementation.
- After agreement, run the smallest real test or other red evidence that proves
  the current gap. This authorizes evidence, not implementation.
- If the evidence disproves the premise, return the result instead of inventing
  a task.
- Prepare a copyable `/goal` only after the DoD and red evidence are sound. Do
  not activate it; the user's `/goal` message starts autonomous implementation.

## Execute

Work autonomously to the agreed goal. Resolve engineering and architecture
choices without narrating internal routing. Investigate suspected blockers and
continue when they are false. Return only for a proven product or business-logic
choice, material infrastructure choice, authority boundary, or external condition that changes the goal.

Do not fix out-of-scope findings inline. Use `ticket` only to search, record a
minimal observation, or update a clear match, then resume the goal. A finding
that blocks the DoD is in scope. Create local recovery commits after coherent,
verified units; never push or change branches without explicit instruction.

## Accept the result

Make the result and evidence durable, then prove the DoD. The bounded route ends
after direct proof. On the complex route, invoke the zero-argument `advisor` on
the final state; reconcile material findings and repeat verification when needed.
Do not declare a complex-route goal done if `advisor` is unavailable.

A goal ends only when every acceptance condition is proven or continuing is
proven impossible without changing the agreed product, infrastructure,
authority, or an unavailable external condition. For impossibility, report the
blocker, evidence, checked alternatives, and why preparation missed it. Do not
repeat an unchanged attempt without a new hypothesis or evidence.

An additional Codex review after the final advisor is reserved for irreversible
data, money, security, broad production impact, or hard-to-reverse architecture.
