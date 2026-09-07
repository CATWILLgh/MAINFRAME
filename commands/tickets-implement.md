# Implement project tickets

This is a user-invocable command. Execute it only because the current invocation explicitly selected it. It takes no arguments: every invocation processes the complete current project queue that is ready for implementation.

Implement each eligible ticket completely within its evidenced boundary, validate the result locally, route it for independent verification, and continue until no ready ticket remains that this command can safely process. Do not discover or refine unrelated problems, verify your own implementation as independent work, deploy, or close tickets during this command.

## Establish the queue and authority

Resolve the current project root, its configured issue route, and the lifecycle states that represent ready work and implemented work awaiting independent verification. Do not use another project's queue or MAINFRAME's central harness-feedback queue.

If the project has no configured issue route or implementation lifecycle, return the exact missing configuration and stop without inventing one. If the queue is external, mutate it only when the current caller supplied that authority. Otherwise return the exact missing write action instead of claiming a completed transition.

The explicit invocation authorizes the local, reversible project and ticket changes required to implement ready tickets in the current checkout. It does not authorize deployment, writes to remote or shared environments, destructive data operations, material infrastructure changes, repository-history changes, commits, or pushes. Preserve the starting branch, unrelated dirty work, existing processes, and user-owned configuration.

## Process exactly one ticket at a time

Read the ready queue afresh. Select one ticket and keep it as the only active ticket until it has been implemented and routed or found ineligible and rerouted. Do not work on separate tickets concurrently. Delegated work, when available and useful, must remain bounded to the same active ticket and return its changes, evidence, limitations, and unverified assumptions for inspection.

After routing the active ticket, refresh the queue and select the next eligible ticket. Do not retry a rerouted or unchanged blocked ticket again in the same run unless its recorded condition has materially changed. Continue with every other ready ticket.

## Revalidate readiness

Confirm against the current project that the ticket still describes an observable problem, the expected behavior is fixed by reliable evidence, its meaningful affected scope is known, its acceptance boundary is testable, and no required premise has become stale. Treat a ready label and earlier conclusions as leads rather than current proof.

Return the ticket to the project's scope-review state without changing implementation code when its evidence, affected boundary, expected behavior, or acceptance condition is materially incomplete or stale. Reject or reroute a disproved or duplicate claim through the configured lifecycle. Continue with the remaining queue.

## Apply the final decision gate

Immediately before changing implementation code, inspect the proposed correction and its meaningful consequences one final time. Determine whether it changes or selects any of the following beyond the behavior already fixed by project instructions, accepted requirements, or an explicit decision recorded in the ticket:

- product behavior, business rules, user-visible semantics, or contractual behavior;
- data meaning, ownership, retention, migration, destructive transformation, or compatibility guarantees;
- public interfaces, security, privacy, access boundaries, or externally relied-on behavior;
- infrastructure topology, shared or live resources, availability, operational risk, recurring cost, or an irreversible rollout path;
- authority or tradeoffs whose practical consequences materially exceed the confirmed ticket boundary.

Do not ask for a decision merely because several sound engineering implementations are possible. Choose ordinary reversible technical details within the confirmed boundary using current project conventions and evidence.

When a material choice remains owned by the user or another named authority, do not implement the ticket. Record the exact unresolved decision, the viable known options, their practical consequences, and why existing project authority does not settle it. Route the ticket to the configured decision state and continue with the next ready ticket.

## Establish pre-change evidence

Before changing behavior, obtain the smallest faithful failing test, reproduction, measurement, or structural proof when it can demonstrate the reported gap. Confirm that it fails for the intended reason rather than unrelated setup. Do not manufacture a ceremonial failing test when a deterministic inspection is stronger or the work is documentation-only, generated, or purely structural.

Inspect a command, script, fixture, setup step, service, or external dependency before using it. Use only the minimum local infrastructure permitted by the effective project instructions. Do not contact or mutate a remote, shared, staging, or production system without separate explicit authority.

## Implement the complete correction

Implement the smallest complete solution for the confirmed ticket across every affected location within its boundary. Preserve existing business and technical behavior outside that boundary. Include the regression protection necessary to keep the confirmed behavior from returning.

Do not leave placeholders, TODOs, suppressed failures, weakened assertions, skipped checks, compatibility debris, or an unrecorded follow-up in place of the required result. If implementation exposes a separate concrete problem, record or reconcile it through the receiving project's problem-recording route when that capability and authority are available, then return to the active ticket without expanding its scope.

If implementation evidence exposes a missing blast radius or a material decision, stop changing that ticket, leave its partial state safe and explicit, record what changed and what remains, route it to scope review or decision as appropriate, and continue only when doing so does not leave the project in a knowingly broken state.

## Validate and route the result

Run the focused proof first, then the nearest relevant fast checks needed to protect the affected business rules, logical behavior, functional behavior, and regression boundary. Use the smallest faithful test set and minimum authorized infrastructure. Run broader or expensive checks only when the changed risk specifically requires them or the current caller assigned a full verification pass.

Confirm that the original red evidence is now green for the intended reason and that no checked adjacent contract regressed. Do not weaken assertions, suppress failures, retry flaky checks until they pass, or treat an unrelated green build as proof. State what each check actually establishes and every material gap.

Append concise implementation locations, pre-change evidence, observed validation, and remaining limitations to the same ticket without duplicating unchanged history. Move it to the configured independent-verification state only when the complete correction and its proportionate local validation are present. Do not archive, close, or independently accept implementation completed in this invocation.

## Complete the command

Continue the one-ticket cycle until a refreshed control pass finds no ready ticket that this command can safely implement under the current evidence and authority. A rerouted ticket is complete for this run only after its exact missing scope, decision, or authority is recorded; it must not prevent processing later tickets.

Return:

- the project queue processed;
- every ticket implemented or rerouted and its resulting state;
- the decisive readiness and final-gate result for each ticket;
- the pre-change evidence, implementation locations, and validation actually observed;
- any ticket or code update that could not be completed and the exact reason;
- confirmation that the final refreshed queue contains no ticket still eligible for implementation under the current conditions.
