# Refine project tickets

This is a user-invocable command. Execute it only because the current invocation explicitly selected it. It takes no arguments: every invocation processes the complete current project queue that is eligible for refinement.

Expand each eligible ticket as far as reliable evidence and the refinement authority allow, route it to the correct next state, and continue until no ticket remains that this command can further process. Do not search the project broadly for new problems or implement fixes during this command.

## Establish the queue and authority

Resolve the current project root, its configured issue route, and the lifecycle states that represent new observations or tickets awaiting more scope evidence. Do not use another project's queue or MAINFRAME's central harness-feedback queue.

If the project has no configured issue route or refinement lifecycle, return the exact missing configuration and stop without inventing one. If the queue is external, mutate it only when the current caller supplied that authority. Otherwise perform the permitted investigation and return the complete ticket updates with the exact missing write action.

The invocation authorizes only the project inspection, safe focused checks, and ticket mutations required for refinement within the supplied environment and authority. It does not authorize implementation, deployment, remote or shared writes, destructive operations, dependency installation, broad infrastructure changes, repository-history changes, commits, or pushes.

Preserve the current checkout, branch, unrelated dirty work, existing processes, and user-owned configuration.

## Process exactly one ticket at a time

Read the current eligible queue afresh. Select one ticket and keep it as the only active ticket until its evidence, scope, identity, and next state are complete. Do not investigate separate tickets concurrently. Delegated work, when available and useful, may gather bounded evidence only for that same active ticket and must return its sources, limitations, and unverified assumptions.

After routing the active ticket, refresh the queue and select the next eligible ticket, including tickets created by a justified split. Do not retry a ticket again in the same run when its recorded evidence gap and available conditions have not changed. Continue with every other eligible ticket.

## Establish what is actually known

Restate the active ticket as a falsifiable claim. Confirm or challenge it using current project evidence rather than memory, ticket age, earlier agent conclusions, or confidence.

Inspect the affected code, configuration, callers, consumers, tests, saved outputs, requirements, and relevant history. Check the most plausible alternative explanation before treating the claim as confirmed. A disagreement between implementations does not establish which behavior is correct.

Use current authoritative primary documentation only when the claim depends on a changing framework, library, protocol, database, service, or external API contract. Verify the version that applies to the current project and state precisely what the source establishes. Do not perform ceremonial external research for a purely internal rule already fixed by project evidence.

Use the smallest safe local test, reproduction, measurement, or structural check that can resolve the claim or an alternative explanation. Inspect the command and its dependencies first so a nominally local check does not contact a remote or shared system. Prefer existing checks; use isolated synthetic data for a disposable probe. Do not run a broad suite, build, benchmark, server, container, migration, or real external integration without a concrete evidentiary need and the required authority.

Do not change application behavior, weaken a test, or implement a proposed fix to make the ticket easier to confirm. Clean up only temporary resources created by this refinement.

## Expand evidence, scope, and identity

Update the ticket with the strongest evidence obtained during this run while preserving its earlier history. Record:

- the exact observed behavior and a reproducible trigger when available;
- the required behavior and the project or external source that defines it;
- confirmation or disconfirmation evidence;
- the affected locations, callers, consumers, and known consequences;
- the alternative explanation checked;
- the limits of the evidence and every material unknown;
- the smallest observable boundary that a later implementation and verification must satisfy.

Do not invent cause, severity, priority, business behavior, or certainty. Do not prescribe implementation details beyond what is necessary to define the confirmed problem and its acceptance boundary.

Keep one independently fixable problem per ticket. Split independent problems into separate records while preserving the origin and links. Search the open queue for semantic duplicates based on behavior, mechanism, and affected boundary. Consolidate only a clear duplicate into the strongest open record, preserve material evidence and history, and follow the configured lifecycle for the duplicate. Never modify an archived or closed record merely to reuse it.

Repeated refinement against unchanged evidence must converge: do not append the same evidence, recreate the same split, repeat an unchanged blocked investigation, or move a ticket between states without new grounds.

## Route the refined ticket

Apply exactly one evidence-backed outcome through the project's configured lifecycle:

- Reject or archive the ticket when the claim is disproved, superseded, or confirmed as a duplicate.
- Mark it ready only when the problem and meaningful scope are confirmed, the expected behavior is fixed by cited evidence, and no product, business-logic, material infrastructure, destructive-action, data, authority, or irreducible preference decision remains.
- Route it to a decision state when one of those choices belongs to the user or another named authority. Record the exact decision, viable known options, and practical consequences without pausing the rest of the refinement campaign.
- Keep or route it to scope review only when a specific unavailable or unauthorized fact, reproduction, measurement, or contract is genuinely required. Record exactly what is missing, why permitted checks could not establish it, and what would unlock the next refinement.

Ordinary engineering and architecture judgment does not become a user decision merely because several implementations are possible. Agent confidence, an appealing solution, or an existing ready label does not establish autonomous eligibility.

## Complete the command

Continue the one-ticket cycle until a refreshed control pass finds no eligible ticket that this command can further expand or route under current evidence and authority. A blocked ticket is complete for this run only after its exact evidence gap or decision is recorded; it must not prevent processing later tickets.

Return:

- the project queue processed;
- every ticket expanded, split, consolidated, rejected, made ready, or routed to a decision or evidence gap;
- the decisive evidence and remaining uncertainty for each outcome;
- ticket updates that could not be written and the exact reason;
- confirmation that the final refreshed queue contains no ticket still eligible for additional refinement under the current conditions.
