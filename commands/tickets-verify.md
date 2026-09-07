# Verify implemented project tickets

This is a user-invocable command. Execute it only because the current invocation explicitly selected it. It takes no arguments: every invocation processes the complete current project queue awaiting independent verification.

Independently verify each eligible implementation, record one evidence-backed verdict, and continue until no ticket remains that this command can reliably process. Do not discover unrelated problems, repair code or tests, deploy, or perform product-wide or release acceptance during this command.

## Establish the queue and authority

Resolve the current project root, its configured issue route, and the lifecycle states that represent implemented work awaiting verification, resolved work, rejected work, ready work, scope review, and decisions. Do not use another project's queue or MAINFRAME's central harness-feedback queue.

If the project has no configured issue route or verification lifecycle, return the exact missing configuration and stop without inventing one. If the queue is external, mutate it only when the current caller supplied that authority. Otherwise perform the permitted checks and return the complete ticket updates with the exact missing write action.

The invocation authorizes project inspection, safe local verification, and the ticket mutations required to record verdicts. It does not authorize changes to implementation code or tests, deployment, writes to remote or shared environments, destructive operations, material infrastructure changes, repository-history changes, commits, or pushes. Preserve the starting branch, unrelated dirty work, existing processes, and user-owned configuration.

## Establish independent execution

Verify a ticket only through an execution trajectory that did not materially author, direct, or accept its implementation or regression protection. Prior implementation notes, claims, commands, and green results are leads, never independent evidence.

When the active trajectory participated in a queued ticket's implementation, do not verify or mutate that ticket from the same trajectory. Use a separate task or a genuinely independent delegated verifier when that capability is available and permitted. Give an independent verifier the ticket, current project state, authority, and required observable boundary, but do not prescribe the verdict or treat the implementer's conclusions as facts. If no independent trajectory is available, return the exact requirement and leave the ticket awaiting verification.

Independence is evaluated per ticket. Continue with other queued tickets only when their verifier is genuinely independent of their implementation.

## Process exactly one ticket at a time

Read the verification queue afresh. Select one independently eligible ticket and keep it as the only active ticket until its verdict and lifecycle transition are complete. Do not verify separate tickets concurrently. Delegated work must remain bounded to the same active ticket and return its sources, observed results, limitations, and unverified assumptions.

After routing the active ticket, refresh the queue and select the next independently eligible ticket. Do not retry a ticket again in the same run when its recorded evidence gap and available conditions have not changed. Continue with every other eligible ticket.

## Reconstruct the claim

Confirm that the ticket still awaits verification. Inspect its full recorded history, the actual current implementation, relevant changes and repository history, affected callers and consumers, regression protection, and generated or delivered artifacts when they are part of the contract.

Restate the original observable problem, the claimed correction, and the business or technical contract that distinguishes success from a plausible false positive. Verify that the ticket identity and acceptance boundary still match the current project. Check the most plausible alternative explanation rather than assuming the implementation caused an observed success.

Use current authoritative primary documentation only when verification depends on a changing external contract. Confirm the version that applies to the project. Repository evidence remains authoritative for project-owned behavior.

## Obtain independent evidence

Use the smallest faithful current reproduction, regression check, measurement, structural inspection, or consumer-facing observation that can prove or disprove the ticket's acceptance boundary. Inspect every command, project script, fixture, setup step, service, and external dependency before using it.

Run focused checks first, followed by the nearest relevant fast checks needed to expose regressions in affected business rules, logical behavior, functional behavior, meaningful error paths, state transitions, and cleanup. Use only the minimum local infrastructure permitted by the effective project instructions. Run broader or expensive checks only when the affected risk specifically requires them or the current caller assigned a full verification pass.

When the result depends on generated output, serialization, installation, migration, concurrency, or another consumer boundary, inspect the real produced shape or deterministic behavior rather than only source code or a mock. Do not convert an unavailable environment, passing mock, coverage percentage, unrelated green suite, prior implementation result, or confidence into evidence for a claim it cannot establish.

Do not modify implementation code, tests, assertions, fixtures, or tracked expected output to obtain a passing result. A disposable verification probe may be created only when it does not change project behavior or persistent state; remove it before recording the verdict.

## Apply the final acceptance gate

Before accepting the ticket as resolved, inspect the actual implementation and the meaningful affected boundary one final time. Establish whether the correction unintentionally changes product behavior, business rules, data meaning or compatibility, public contracts, security, privacy, access boundaries, or infrastructure behavior beyond the requirements and decisions already recorded for the ticket.

Require proportionate evidence for the material adjacent risks revealed by that inspection. Do not claim exhaustive absence of regression; state every relevant boundary that was not observable under the available authority and environment.

If verification exposes an unresolved material choice owned by the user or another named authority, record the exact choice, viable known options, practical consequences, and missing authority, then route the ticket to the configured decision state. Do not invent a decision or accept the implementation. Ordinary reversible engineering choices already within the confirmed ticket boundary do not require renewed user approval.

## Record exactly one verdict

Preserve the ticket identity and accumulated evidence. Append only the new independent observations, commands or checks actually performed, their results, and material limitations. Do not duplicate unchanged history. Apply exactly one transition through the project's configured lifecycle:

- Move a proven correction to the immutable resolved archive only when the original problem is no longer reproducible for the intended reason, the acceptance boundary is demonstrated, and the final acceptance gate is satisfied.
- Return an incomplete or incorrect implementation to ready work with precise failed-verification evidence and without repairing it inline.
- Return work with a materially missed or stale affected boundary to scope review.
- Route a newly exposed material product, business, data, security, infrastructure, destructive-action, or authority choice to the decision state.
- Move a disproved, superseded, or confirmed duplicate claim to the immutable rejected archive.
- Leave it awaiting verification only when a specific unavailable environment, permission, dependency, observation, or independent trajectory prevents a reliable verdict; record exactly what would unlock verification.

Never edit, reopen, rename, or move an archived ticket. A later occurrence is a new observation with its own identity. If verification reveals a separate concrete problem, record or reconcile it through the receiving project's problem-recording route when that capability and authority are available, then return to the active ticket without investigating or fixing it inline.

Repeated verification against unchanged state must converge: do not append the same evidence, repeat an unchanged blocked check, duplicate a transition, or touch an already archived ticket.

## Complete the command

Continue the one-ticket cycle until a refreshed control pass finds no independently eligible ticket that this command can further verify under the current evidence, environment, and authority. A blocked or non-independent ticket is complete for this run only after the exact missing condition is recorded; it must not prevent processing later tickets.

Return:

- the project verification queue processed;
- the independence basis for every checked ticket;
- every ticket's verdict and resulting lifecycle state;
- the independently observed evidence and the meaningful adjacent contracts checked;
- every unobserved material boundary and the exact reason;
- confirmation that the final refreshed queue contains no ticket still eligible for verification under the current conditions.
