# Implement project tickets

This is a user-invocable command. Execute it only because the current invocation explicitly selected it. It takes no arguments: every invocation processes the complete current project queue that is ready for implementation.

Implement each eligible ticket completely within its evidenced boundary, validate the result locally, route it for independent verification, and continue until no ready ticket remains that this command can safely process. Do not discover or refine unrelated problems, verify your own implementation as independent work, deploy, or close tickets during this command.

When the user starts a native goal and then invokes this command separately, process the campaign under that existing goal. Preserve progress through continuations; do not create another goal or stop after the first completed ticket.

## Read the initialized ticket contract

Read `docs/tickets/AGENTS.md` and require the `mainframe-tickets-v1` contract before queue writes. If the root, contract, or required layout is missing or conflicts with effective project rules, report that `mainframe-tickets-init` must initialize or reconcile it; do not run initialization implicitly, invent another tracker, or migrate unrelated records. Use `docs/tickets/` in the current project only. The directory is state: do not add a YAML `status` field. Preserve string IDs, required frontmatter, meaningful evidence and links. Exclude `.campaigns/` and `.migration/` from every ticket scan.

Select only `docs/tickets/open/ready/` records with `execution: autonomous` and an evidenced `Autonomous implementation boundary`. Do not consume `user-approved` records through this queue-wide command. Keep the active record in ready while implementing. Add `Implementation` with source locations, pre-change evidence, checks, limitations and checkpoint references; preserve investigation, acceptance, identity and execution metadata. Move a completed verified correction to `open/needs-verification/`; route missing evidence to `open/needs-scope-review/`, unresolved user choices to `open/needs-decision/`, and disproved or duplicate claims to `archive/rejected/` with evidence. Save continuation and resulting commit identities under `.campaigns/`. Preserve ignored record ownership and validate YAML, destination and links after each move.

## Establish the queue and authority

Use the initialized local queue and the stage-specific destinations above. A missing or conflicting contract is an initialization issue, not permission to invent lifecycle states. Preserve the project's tracked or ignored ownership.

The explicit invocation authorizes the local, reversible project and ticket changes required to implement ready tickets in the current checkout. It does not authorize deployment, writes to remote or shared environments, destructive data operations, material infrastructure changes, destructive history changes, or pushes. Unless the caller or effective project policy forbids commits, the invocation also authorizes a local Conventional Commit for each completed, verified ticket. It does not authorize a push. Preserve the starting branch, unrelated dirty work, existing processes, and user-owned configuration.

## Process exactly one ticket at a time

Read the ready queue afresh. Select one ticket and keep it as the only active ticket until it has been implemented and routed or found ineligible and rerouted. Do not work on separate tickets concurrently. Delegated work, when available and useful, must remain bounded to the same active ticket and return its changes, evidence, limitations, and unverified assumptions for inspection.

After routing the active ticket, refresh the queue and select the next eligible ticket. Do not retry a rerouted or unchanged blocked ticket again in the same run unless its recorded condition has materially changed. Continue with every other ready ticket.

Save evidence and meaningful progress in the active ticket as work proceeds. Keep resumable campaign state in the established project goal or agent-state location: active ticket, completed steps, remaining work, handled records, validation, commit references, and pending writes. After a context change, inspect the actual diff, ticket state, and commits before resuming so completed work is not repeated. Do not use the conversation as the only record.

If a ticket update cannot be written, preserve its complete proposed update and missing action in permitted campaign state and continue with independent ready work when the checkout remains safe. Do not claim the persistent queue changed or successful campaign completion while required writes or checkpoints remain unresolved.

## Revalidate readiness

Confirm against the current project that the ticket still describes an observable problem, the expected behavior is fixed by reliable evidence, its meaningful affected scope is known, its acceptance boundary is testable, and no required premise has become stale. Treat a ready label and earlier conclusions as leads rather than current proof.

Return the ticket to the project's scope-review state and directory without changing implementation code when its evidence, affected boundary, expected behavior, or acceptance condition is materially incomplete or stale. Reject or reroute a disproved or duplicate claim through the initialized lifecycle. Continue with the remaining queue.

## Apply the final decision gate

Before changing implementation code, evaluate the proposed correction using the
readiness evidence already collected; inspect further only for unresolved
consequences. Determine whether it changes or selects any of the following beyond
the behavior already fixed by project instructions, accepted requirements, or an
explicit decision recorded in the ticket:

- product behavior, business rules, user-visible semantics, or contractual behavior;
- data meaning, ownership, retention, migration, destructive transformation, or compatibility guarantees;
- public interfaces, security, privacy, access boundaries, or externally relied-on behavior;
- infrastructure topology, shared or live resources, availability, operational risk, recurring cost, or an irreversible rollout path;
- authority or tradeoffs whose practical consequences materially exceed the confirmed ticket boundary.

Do not ask for a decision merely because several sound engineering implementations are possible. Choose ordinary reversible technical details within the confirmed boundary using current project conventions and evidence.

When a material choice remains owned by the user or another named authority, do not implement the ticket. Record the exact unresolved decision, the viable known options, their practical consequences, and why existing project authority does not settle it. Route the ticket to the configured decision state and directory, preserving its identity and links, and continue with the next ready ticket.

## Use current external evidence

Use current authoritative internet sources and available MCP resources to resolve relevant implementation contracts, compatibility, supported APIs, and uncertain engineering choices. Inspect the applicable project versions and prefer primary documentation, maintained source, and specifications. Reuse current adequate evidence from refinement; update it when the relevant contract or version changed. Record the specific source, applicable version, conclusion, and material uncertainty in the ticket. External research is part of the work when it can affect correctness, not a requirement to collect decorative links for an entirely internal rule. Do not expose credentials or private project material to external sources; MCP availability does not expand access authority.

## Establish pre-change evidence

Before changing behavior, obtain the smallest faithful failing test, reproduction, measurement, or structural proof when it can demonstrate the reported gap. Confirm that it fails for the intended reason rather than unrelated setup. Do not manufacture a ceremonial failing test when a deterministic inspection is stronger or the work is documentation-only, generated, or purely structural.

Inspect a command, script, fixture, setup step, service, or external dependency before using it. Use only the minimum local infrastructure permitted by the effective project instructions. Access to project remote, shared, staging, or production environments requires existing explicit authority; reuse it when supplied. This boundary does not prohibit public documentation research.

## Implement the complete correction

Implement the smallest complete solution for the confirmed ticket across every affected location within its boundary. Preserve existing business and technical behavior outside that boundary. Include the regression protection necessary to keep the confirmed behavior from returning.

Do not leave placeholders, TODOs, suppressed failures, weakened assertions, skipped checks, compatibility debris, or an unrecorded follow-up in place of the required result. If implementation exposes a separate concrete problem, record or reconcile it through the receiving project's problem-recording route when that capability and authority are available, then return to the active ticket without expanding its scope.

If implementation evidence exposes a missing blast radius or a material decision, stop changing that ticket, leave its partial state safe and explicit, record what changed and what remains, route it to scope review or decision as appropriate, and continue only when doing so does not leave the project in a knowingly broken state.

## Validate and route the result

Run the focused proof first, then the nearest relevant fast checks needed to protect the affected business rules, logical behavior, functional behavior, and regression boundary. Use the smallest faithful test set and minimum authorized infrastructure. Run broader or expensive checks only when the changed risk specifically requires them or the current caller assigned a full verification pass.

Confirm that the original red evidence is now green for the intended reason and that no checked adjacent contract regressed. Do not weaken assertions, suppress failures, retry flaky checks until they pass, or treat an unrelated green build as proof. State what each check actually establishes and every material gap.

Consolidate implementation locations, relevant external sources, pre-change evidence, observed validation, and remaining limitations in the same ticket. Give the independent verifier enough context to reproduce the check and distinguish success from a false positive without this conversation. Move the ticket to the configured independent-verification state and directory only when the complete correction and its proportionate local validation are present. Validate project YAML/Markdown fields, links, and the move so no stale duplicate remains in the ready directory. Do not archive, close, or independently accept implementation completed in this invocation.

## Checkpoint the completed ticket

Before starting the next ticket, inspect the diff and create a local Conventional Commit for the completed verified correction, including its ticket transition when those files are tracked. Reference the ticket identity in the commit message. Stage only this ticket's owned changes and preserve unrelated changes and partial staging. Keep intentionally ignored tickets ignored; do not force-add them.

Record the resulting commit identity in the established campaign state or ticket mechanism. Do not create an amendment loop merely to put a commit's own hash inside itself. If there are no code changes, document why and route the ticket appropriately instead of making an empty implementation commit. Do not commit unfinished work after discovering that a ticket requires a user decision. If policy forbids commits or ownership cannot safely be separated, preserve verified work, record the exact checkpoint limitation, and report it without claiming a commit occurred.

## Complete the command

Continue the one-ticket cycle until a refreshed control pass finds no additional ready ticket that this command can safely implement under the current evidence and authority. A rerouted ticket is handled for this run only after its exact missing scope, decision, or authority is recorded or returned as a complete proposed update; it must not prevent processing later tickets.

When a refreshed queue leaves no further eligible engineering work, confirm that all results and transitions are persisted and required permitted commits are present before completing the active goal. Tickets correctly routed to user decisions or unavailable investigation are accounted for, not silently abandoned. User stops, native execution limits, and unresolved write/checkpoint blockers require an accurate stopped or resumable state rather than a success claim.

Return the queue processed, tickets implemented or rerouted, resulting states and paths, implementation locations, local commits or explicit policy exceptions, and observed validation. Include any material decision or incomplete write and what is needed next. State whether the refreshed queue leaves further permitted implementation. Omit empty categories and distinguish persisted transitions from proposals.
