# Review and repair the current branch before release

Run only on explicit invocation. It takes no arguments. Review the current
branch and relevant uncommitted work before integration or release. Correct
evidenced regressions and engineering defects in scope, verify them, and make
local checkpoints. Follow any narrower assignment, including read-only review.
This command supplies local repair and commit authority. A push, merge, release,
or live provider action needs its own authority. Preserve the current branch,
checkout, unrelated work, and partial staging.

If the user already started a goal for this work, carry it through completion.
Resume from the actual branch, verified batches, and outstanding decisions.

## Establish what is pending

- Inspect the active worktree, branch, `HEAD`, staged and unstaged changes, and
  relevant untracked source files. Identify which existing changes belong to
  the assigned result before adopting them. Exclude secrets, scratch files,
  generated residue, and work whose ownership is unclear from commits.
- Determine the intended integration target from the assigned scope, project
  workflow, or current merge request. Use ancestry to find the branch delta.
  On a release or integration branch, use the verified deployed or last
  accepted revision when that defines the pending work. Use a user-supplied
  stage or other comparison only for the stated scope. If a comparison is
  missing, review what can be bounded and report the exact gap.
- Check publication against the intended remote ref and delivery against the
  actual target environment. Use production as the default delivery target
  when the project has one. Keep test and stage evidence tied to those
  environments. Use current authorized read-only evidence and distinguish it
  from cached refs. Map the deployed artifact to its source revision for each
  affected deployable unit. A green pipeline or branch name alone cannot
  establish deployment. Report unknowns explicitly.
- Include unpublished local commits and relevant dirty work, and include
  published branch changes still pending release. Check for equivalent changes
  delivered under another commit before repeating them. If history diverged,
  inspect the graph and the actual behavior without changing history.

## Review related changes in dependency order

Start with the oldest relevant changes and work toward the tip in coherent
batches. Follow dependencies across commits, callers, data, configuration, and
consumers. Account for merges, reverts, and superseded changes. Use the final
integrated tree to verify current behavior. A batch should cover a usable slice
and its affected neighbors, including paths that already worked.

Compare the intended business contract with the previous accepted behavior,
the implementation, and what users can actually complete. Preserve intentional
changes. Reuse an existing working path when it satisfies the contract. Look
for duplications, lost features, extra layers, and reachable failure cases.
Prefer the smallest complete fix with clear ownership and bounded recovery.
Delegate only when it improves the result. Select the role, model, and effort
for the actual work, then verify its contribution in the integrated path.

Review these risks where the changed paths expose them.

- **User and API behavior.** Exercise affected roles and existing user journeys
  through their normal entrypoints. Verify authorization, compatibility, error
  handling, and recovery. UI states explain what happened and offer an action
  when the user can take one. Keep operational detail in diagnostics.
- **Queues and dependencies.** Trace sync and async boundaries, admission,
  ordering, capacity, and durable completion. Exercise overlapping work,
  slow dependencies, and retry or cancellation when relevant. Reconcile
  ambiguous external outcomes before replaying them. Look for lost or
  repeated effects and starvation of existing work.
- **Database and performance.** Separate pool wait, lock wait, query work,
  and queue delay. Check transaction scope and work that scales with data or
  traffic. Use realistic load and compare successful completion, latency,
  and limiting resources. Add a regression that can reject the observed cost
  or contention. Use the correct engine when semantics matter.
- **Diagnostics and documentation.** Use `mainframe-logging` for changed
  logs or failure diagnostics. Match API documentation to actual requests,
  responses, errors, examples, and permissions. Expose what each audience
  needs. Keep partner docs scoped to public behavior and put useful operational
  detail in the appropriate admin material.
- **Deployment and recovery.** If the change affects rollout, migrations, or
  recovery, inspect compatibility, readiness, and user-route continuity
  across the handoff. Use authorized evidence. Reuse adequate recovery points.
  When a new backup is necessary and authorized, identify restore proof,
  retention, and cleanup ownership.

## Repair what the evidence settles

Fix technical defects and business-rule regressions whose intended result is
unambiguous from the accepted contract and evidence. Consult current primary
documentation for relevant external behavior. Other systems can inform a
choice, but project policy and permission boundaries need their own evidence.
Raise a consequential conflict before implementing a proposed approach or an
alternative. Seek the caller's decision on materially changed product rules,
access, external effects, or ongoing cost. In particular, keep partner and
operator permissions within their established limits.

Record unresolved decisions through the project's authorized ticket route.
State the affected behavior, evidence, viable choices, consequences, and the
acceptance condition. If recording is unavailable, return a ticket-ready
handoff. Continue other authorized batches. Complete settled work here.

## Verify cumulatively and checkpoint

Use `mainframe-testing`. Reproduce the failure for an in-scope fix, verify
the correction through the owning path, and test relevant neighboring
behavior. Check that assertions can catch the failure they claim to cover.
After each batch, verify its result and reconsider earlier guarantees in the
combined tree. Rerun affected checks from earlier batches and reuse prior
evidence only where the new changes cannot invalidate it. Run a final check
through the affected user or system journey at the integrated revision.

Keep the local loop focused and resource-bounded. Use isolated verified local
PostgreSQL when needed. Other real dependencies and expensive suites default
to CI under the task's authority. Use synthetic inputs and faithful fixtures
within their actual evidence limits. When optimizing tests or CI, measure
the bottleneck and keep meaningful assertions, scenarios, and required gates.
Inspect actual CI results for the relevant revision and event when required.

Checkpoint coherent, verified batches with local Conventional Commits. Include
pre-existing changes only when they belong to the reviewed result and pass
its checks. Stage only owned changes. If unrelated staging cannot be safely
separated, preserve it and report the exact pending checkpoint.

## Finish with a concise report

Recheck the final revision, pending range, and worktree. Finish when each
batch has been reviewed and every available in-scope fix and required check
is complete. Report what was fixed, the meaningful checks and measured
changes, local commits, decision tickets, and the actual publication and
release state. Name unresolved decisions and any check still blocked, with
the evidence or authority needed next. Use plain Russian for the user-facing
report unless the caller requests another language.
