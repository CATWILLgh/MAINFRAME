# Verify implemented project tickets

This is a user-invocable command. Execute it only because the current invocation explicitly selected it. It takes no arguments: every invocation processes the complete current project queue awaiting independent verification.

Independently verify each eligible implementation, record one evidence-backed verdict, and continue until no ticket remains that this command can reliably process. Do not discover unrelated problems, repair code or tests, deploy, or perform product-wide or release acceptance during this command.

When the user starts a native goal and then invokes this command separately, process the queue under that existing goal. The ticket-only write boundary applies to the entire verification campaign, including continuations and delegated work. Do not create a second goal or switch to implementation after finding a failed check.

## Read the initialized ticket contract

Read `docs/tickets/AGENTS.md` and check its directory, record-format, and lifecycle rules before queue writes. If the root, contract, or required layout is missing or conflicts with effective project rules, report that `mainframe-tickets-init` must initialize or reconcile it; do not run initialization implicitly, invent another tracker, or migrate unrelated records. Use `docs/tickets/` in the current project only. The directory is state: do not add a YAML `status` field. Preserve string IDs, required frontmatter, meaningful evidence and links. Exclude `.campaigns/` and `.migration/` from every ticket scan.

Select only `docs/tickets/open/needs-verification/`, preserving the recorded execution route. Add `Verification` with the independence basis, current checks, verdict, adjacent risk evidence and limitations, plus a `Blocker` or `User decision` section when required. Move a proved correction to `archive/resolved/`, a failed implementation to `open/ready/`, missed investigation to `open/needs-scope-review/`, user-owned choices to `open/needs-decision/`, and disproved, superseded or duplicate claims to `archive/rejected/`. A blocked observation may remain in needs-verification with the exact resumption condition. Preserve IDs, required YAML and execution markers; returning a user-approved record to ready does not convert it into autonomous work. Update only ticket records and their paths/links; progress stays in them and native goal state. Do not edit `.campaigns/`, root rules, README, or recovery files during verification.

## Establish the queue and authority

Use the initialized local queue and the stage-specific destinations above. A missing or conflicting contract is an initialization issue, not permission to invent lifecycle states. Preserve the project's tracked or ignored ownership.

The invocation authorizes project inspection, safe local verification, and ticket mutations required to preserve evidence and record verdicts. Only ticket records may receive persistent project edits: do not change source code, tests, fixtures, snapshots, dependencies, lockfiles, configuration, project instructions, skills, or other documentation, even to repair an obvious typo or unblock a check. It does not authorize changes to implementation code or tests, deployment, writes to remote or shared environments, destructive operations, material infrastructure changes, repository-history changes, commits, or pushes. Preserve the starting branch, unrelated dirty work, existing processes, and user-owned configuration.

## Establish independent execution

Verify a ticket only through an execution trajectory that did not materially author, direct, or accept its implementation or regression protection. Prior implementation notes, claims, commands, and green results are leads, never independent evidence.

When the active trajectory participated in a queued ticket's implementation, do not verify or mutate that ticket from the same trajectory. Use a separate task or a genuinely independent delegated verifier when that capability is available and permitted. Give an independent verifier the ticket, current project state, authority, and required observable boundary, but do not prescribe the verdict or treat the implementer's conclusions as facts. If no independent trajectory is available, return the exact requirement and leave the ticket awaiting verification.

Independence is evaluated per ticket. Continue with other queued tickets only when their verifier is genuinely independent of their implementation.

## Process exactly one ticket at a time

Read the verification queue afresh. Select one independently eligible ticket and keep it as the only active ticket until its verdict and lifecycle transition are complete. Do not verify separate tickets concurrently. Delegated work must remain bounded to the same active ticket and inherit the ticket-only write restriction. Return sources, observed results, limitations, and unverified assumptions. Delegation must never be used to perform a prohibited repair.

After routing the active ticket, refresh the queue and select the next independently eligible ticket. Do not retry a ticket again in the same run when its recorded evidence gap and available conditions have not changed. Continue with every other eligible ticket.

Persist material verification evidence and remaining checks in the active ticket as work proceeds. Use those ticket records and the existing native goal state to resume after context changes; do not create or edit a separate project progress file. Recheck the current implementation revision or diff before reusing saved evidence. A context change does not justify replaying unchanged blocked checks.

If a ticket update cannot be written, retain the complete proposed update and missing action through the available native goal mechanism, report the limitation, and continue with other eligible tickets. Do not claim persistence or successful campaign completion while required ticket writes remain pending.

## Reconstruct the claim

Confirm that the ticket still awaits verification. Inspect its full recorded history, the actual current implementation, relevant changes and repository history, affected callers and consumers, regression protection, and generated or delivered artifacts when they are part of the contract.

Restate the original observable problem, the claimed correction, and the business or technical contract that distinguishes success from a plausible false positive. Verify that the ticket identity and acceptance boundary still match the current project. Check the most plausible alternative explanation rather than assuming the implementation caused an observed success.

Use current authoritative internet sources and available MCP resources when they can establish the expected contract, compatibility, or correctness of the implementation. Confirm applicable versions and save specific sources and their conclusions in the ticket. Inspect evidence from prior stages rather than accepting their interpretation as independent proof; reuse applicable sources without ceremonial repeated searches. Repository evidence remains authoritative for project-owned behavior. External access stays within existing authority and must not expose secrets or private project material.

## Obtain independent evidence

Use the smallest faithful current reproduction, regression check, measurement, structural inspection, or consumer-facing observation that can prove or disprove the ticket's acceptance boundary. Inspect every command, project script, fixture, setup step, service, and external dependency before using it.

Run focused checks first, followed by the nearest relevant fast checks needed to expose regressions in affected business rules, logical behavior, functional behavior, meaningful error paths, state transitions, and cleanup. Use only the minimum local infrastructure permitted by the effective project instructions. Run broader or expensive checks only when the affected risk specifically requires them or the current caller assigned a full verification pass.

When the result depends on generated output, serialization, installation, migration, concurrency, or another consumer boundary, inspect the real produced shape or deterministic behavior rather than only source code or a mock. Do not convert an unavailable environment, passing mock, coverage percentage, unrelated green suite, prior implementation result, or confidence into evidence for a claim it cannot establish.

Do not modify implementation code, tests, assertions, fixtures, or expected output for any reason. Run checks without autofix, snapshot updates, code generation into project paths, dependency installation, or other persistent project changes. If a faithful check requires such a repair, record the blocker and route the ticket instead of making the repair.

A disposable verification probe and transient check output may live outside the project in an authorized temporary location, without modifying the implementation under review or contacting unauthorized systems. Remove only resources created by that probe. Inspect the relevant diff before and after checks to detect accidental non-ticket edits; preserve pre-existing or concurrent work. If a check unexpectedly mutates project files, stop that check, report the exact change and do not treat the modified result as verification evidence or blindly reset user work.

## Apply the final acceptance gate

Before accepting the ticket as resolved, evaluate the collected implementation
and verification evidence for unintended changes to product behavior, business
rules, data meaning or compatibility, public contracts, security, privacy, access
boundaries, or infrastructure beyond the ticket's requirements and decisions.
Repeat inspection or checks only when changed state or an unresolved material gap
makes the existing evidence insufficient.

Require proportionate evidence for the material adjacent risks revealed by that inspection. Do not claim exhaustive absence of regression; state every relevant boundary that was not observable under the available authority and environment.

If verification exposes an unresolved material choice owned by the user or another named authority, record the exact choice, viable known options, practical consequences, and missing authority, then route the ticket to the configured decision state. Do not invent a decision or accept the implementation. Ordinary reversible engineering choices already within the confirmed ticket boundary do not require renewed user approval.

## Record exactly one verdict

Preserve the ticket identity and accumulated evidence. Append only the new independent observations, commands or checks actually performed, their results, and material limitations. Do not duplicate unchanged history. Apply exactly one transition through the initialized lifecycle, updating the required fields and moving the ticket to the corresponding directory. Validate YAML/Markdown, writable ticket links, and record identity so the transition leaves no stale duplicate:

- Move a proven correction to the configured resolved terminal state or archive only when the original problem is no longer reproducible for the intended reason, the acceptance boundary is demonstrated, and the final acceptance gate is satisfied.
- Return an incomplete or incorrect implementation to ready work with precise failed-verification evidence and without repairing it inline.
- Return work with a materially missed or stale affected boundary to scope review.
- Route a newly exposed material product, business, data, security, infrastructure, destructive-action, or authority choice to the decision state.
- Move a disproved, superseded, or confirmed duplicate claim to the configured rejected terminal state or archive.
- Leave it awaiting verification only when a specific unavailable environment, permission, dependency, observation, or independent trajectory prevents a reliable verdict; record exactly what would unlock verification.

Preserve terminal records and their accumulated evidence as immutable history; do not edit, reopen, rename, or move them in this command. A later occurrence is a new observation with its own identity through the configured project route. If verification reveals a separate concrete problem, record or reconcile it through the receiving project's problem-recording route when that capability and authority are available, then return to the active ticket without investigating or fixing it inline.

Repeated verification against unchanged state must converge: do not append the same evidence, repeat an unchanged blocked check, duplicate a transition, or touch an already archived ticket.

## Complete the command

Continue the one-ticket cycle until a refreshed control pass finds no additional independently eligible ticket that this command can further verify under the current evidence, environment, and authority. A blocked or non-independent ticket is handled for this run only after the exact missing condition is recorded or returned to the current recipient; it must not prevent processing later tickets.

Complete the active goal successfully only when a refreshed queue leaves no further independently eligible verification under current conditions and all required observations and transitions are persisted. Tickets with specific recorded blockers remain unresolved; queue processing does not mean every implementation passed. User stop or native execution limits require an accurate stopped or resumable state, not a successful completion claim.

Return the queue processed and, for each checked ticket, the independence basis, verdict, resulting state, decisive observations, and material verification gaps. State whether the refreshed queue leaves further permitted independent verification. Omit empty categories and distinguish persisted transitions from proposals.
