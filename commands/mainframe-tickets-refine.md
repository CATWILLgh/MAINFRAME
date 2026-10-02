# Refine project tickets

This is a user-invocable command. Execute it only because the current invocation explicitly selected it. It takes no arguments: every invocation processes the complete current project queue that is eligible for refinement.

Investigate each eligible ticket deeply: establish its code execution path, cause or supported mechanism, blast radius, and relationship to other tickets. Consolidate the evidence, route it to the correct next state, and continue until no ticket remains that this command can further process. Do not search the project broadly for new problems or implement fixes during this command.

When the user first starts a native goal and then invokes this command in a separate message, perform the campaign under that existing goal. Do not create a second goal or interpret the command as a request to investigate just one ticket.

## Establish the queue and authority

Resolve the current project root, its configured issue route, ticket identity and YAML/Markdown requirements, and the lifecycle states that represent new observations or tickets awaiting more scope evidence. Preserve the project's schema and validate ticket structure and links after updates. Do not use another project's queue or MAINFRAME's central harness-feedback queue.

If the project has no configured issue route or refinement lifecycle, return the exact missing configuration and stop without inventing one. If the queue is external, mutate it only when the current caller supplied that authority. Otherwise perform the permitted investigation and return the complete ticket updates with the exact missing write action.

The invocation authorizes only the project inspection, safe focused checks, and ticket mutations required for refinement within the supplied environment and authority. It does not authorize implementation, deployment, remote or shared writes, destructive operations, dependency installation, broad infrastructure changes, repository-history changes, commits, or pushes.

Preserve the current checkout, branch, unrelated dirty work, existing processes, and user-owned configuration.

## Process exactly one ticket at a time

Read the current eligible queue afresh. Select one ticket and keep it as the only active ticket until its evidence, scope, identity, and next state are complete. Do not investigate separate tickets concurrently. Delegated work, when available and useful, may gather bounded evidence only for that same active ticket and must return its sources, limitations, and unverified assumptions.

After routing the active ticket, refresh the queue and select the next eligible ticket, including tickets created by a justified split. Do not retry a ticket again in the same run when its recorded evidence gap and available conditions have not changed. Continue with every other eligible ticket.

Persist useful evidence in the active ticket as it is established, without waiting for the entire investigation to finish. Keep resumable campaign progress in the project's established goal or agent-state location: active ticket, completed investigation steps, remaining leads, handled ticket identities and their evidence boundaries, and pending writes. Preserve this state across context changes; do not use the conversation as the only record or invent a new storage convention.

If a ticket update cannot be written, preserve the complete proposed update and missing action in permitted campaign state and continue with other tickets. Reconsider an unchanged blocked ticket only when its state, evidence, or authority materially changes. Do not claim the persistent queue changed or mark the campaign successfully complete while required writes remain pending.

## Establish what is actually known

Restate the active ticket as a falsifiable claim. Confirm or challenge it using current project evidence rather than memory, ticket age, earlier agent conclusions, or confidence.

Inspect the affected code, configuration, callers, consumers, tests, saved outputs, requirements, and relevant history. Discovery evidence is a starting point, not a substitute for this investigation. Reuse evidence only after establishing that it still applies; do not repeat an adequate check solely for ceremony. Check plausible alternative explanations before treating the claim as confirmed. A disagreement between implementations does not establish which behavior is correct.

Trace the real execution path from its entrypoint through registration, dispatch, relevant branches, persistence, external calls, side effects, and downstream consumers. Cite actual source locations and explain how inputs and state lead to the observed result. Mark unobserved runtime links as unknown rather than treating static reachability as execution proof.

Investigate blast radius beyond the first failing location: shared helpers and other callers, affected user scenarios, data readers and writers, public contracts, failure/retry behavior, and compatibility or recovery consequences where relevant. Follow each concrete material lead until its relationship is established or an exact evidence gap is recorded. Distinguish observed impact, impact implied by demonstrated shared behavior, and unverified possibilities. Do not invent an exhaustive checklist for unrelated domains or claim completeness from inspecting the named file alone.

Use current authoritative primary documentation, internet sources, and available MCP resources when they can resolve the claim, expected behavior, or affected boundary. Verify the version that applies to the current project and preserve the specific source, its applicable version, and what it establishes in the ticket. Treat MCP results as evidence with an identified source and access boundary, not authority to broaden the investigation into unrelated or protected systems. Do not perform ceremonial external research for a purely internal rule already fixed by project evidence.

Use the smallest safe local test, reproduction, measurement, or structural check that can resolve the claim or an alternative explanation. Inspect the command and its dependencies first so a nominally local check does not contact a remote or shared system. Prefer existing checks; use isolated synthetic data for a disposable probe. Do not run a broad suite, build, benchmark, server, container, migration, or real external integration without a concrete evidentiary need and the required authority.

Do not change application behavior, weaken a test, or implement a proposed fix to make the ticket easier to confirm. Clean up only temporary resources created by this refinement.

## Expand evidence, scope, and identity

Update the ticket with the strongest evidence obtained during this run while preserving its earlier history. Record:

- the exact observed behavior and a reproducible trigger when available;
- the required behavior and the project or external source that defines it;
- confirmation or disconfirmation evidence;
- the traced execution path and relevant source locations;
- the blast radius, affected callers and consumers, direct and indirect consequences, and evidence for each material boundary;
- the alternative explanation checked;
- the limits of the evidence and every material unknown;
- the smallest observable boundary that a later implementation and verification must satisfy.

Do not invent cause, severity, priority, business behavior, or certainty. Do not prescribe implementation details beyond what is necessary to define the confirmed problem and its acceptance boundary.

## Resolve duplicates and mixed problems

As the investigation establishes mechanism and blast radius, search the open queue for related records. Compare causes or demonstrated mechanisms, execution paths, triggering conditions, and affected boundaries; different symptoms can describe the same problem. Similar titles, files, or symptoms alone do not prove duplication.

Consolidate confirmed duplicates into one suitable open primary ticket. Merge useful evidence into its relevant sections, preserve identity and meaningful history, and add explicit links. Save and verify the consolidated primary record before routing the other records through the project's duplicate outcome. Do not discard evidence or close a supposed duplicate whose relationship remains uncertain.

Keep related but independently fixable problems separate and link their relationship. Split a ticket that mixes independent problems into records with distinct boundaries and preserved origin links. Include new eligible records in the remaining campaign queue. Resolve these identity decisions for the active ticket before moving to the next investigation; comparison of related records is part of that investigation, not permission to run separate tickets concurrently.

Never modify archived or closed records merely to reuse them. A demonstrated recurrence should use the project's new linked observation route rather than be dismissed as an already resolved duplicate.

Repeated refinement against unchanged evidence must converge: do not append the same evidence, recreate the same split, repeat an unchanged blocked investigation, or move a ticket between states without new grounds.

## Route the refined ticket

Apply exactly one evidence-backed outcome through the project's configured lifecycle:

- Reject or archive the ticket when the claim is disproved, superseded, or confirmed as a duplicate.
- Mark it ready only when the problem, execution path, and meaningful blast radius are established with no unresolved material investigation lead, the expected behavior is fixed by cited evidence, and no product, business-logic, material infrastructure, destructive-action, data, authority, or irreducible preference decision remains.
- Route it to a decision state when one of those choices belongs to the user or another named authority. Record the exact decision, viable known options, and practical consequences without pausing the rest of the refinement campaign.
- Keep or route it to scope review only when a specific unavailable or unauthorized fact, reproduction, measurement, or contract is genuinely required. Record exactly what is missing, why permitted checks could not establish it, and what would unlock the next refinement.

Ordinary engineering and architecture judgment does not become a user decision merely because several implementations are possible. Agent confidence, an appealing solution, or an existing ready label does not establish autonomous eligibility.

## Complete the command

Continue the one-ticket cycle until a refreshed control pass finds no additional ticket that this command can further investigate or route under current evidence and authority, including split records and primary records expanded by consolidation. Context changes and native execution limits require a saved continuation, not a completion claim. A blocked ticket is handled for this run only after its exact evidence gap or decision is recorded or returned as a complete proposed update; it must not prevent processing later tickets.

Finish the active goal successfully only after the eligible queue is exhausted for current conditions, all handled tickets have an evidence-backed outcome, and required ticket updates are persisted. A genuine blocker or user stop must follow native goal status rules and must not be represented as successful queue processing.

Return the queue processed and each changed ticket's outcome, decisive trace and blast-radius evidence, consolidation or split links, and material uncertainty. Include proposed updates that could not be written and the exact missing action. State whether the refreshed queue leaves further permitted refinement. Omit empty categories and distinguish persisted transitions from proposals.
