# Find project ticket candidates

This is a user-invocable command. Execute it only because the current invocation explicitly selected it. It takes no arguments: every invocation covers the complete current project.

Start discovery from the current project state every time. Find concrete problem candidates across the complete project, reconcile them with the receiving project's configured open issue queue, and return an evidence-based coverage report. Earlier runs, remembered coverage, and existing tickets are leads and deduplication inputs, never substitutes for a fresh pass. Do not implement, fully refine, prioritize, decide, or close tickets during this command.

## Establish the boundary

Resolve the current project root and its configured issue route from the effective project harness. Do not use another repository's queue or MAINFRAME's central harness-feedback queue. If the project has no configured issue route, return the exact missing configuration and ticket-ready findings; do not invent a tracker or initialize a queue as a side effect of discovery.

The invocation authorizes read-only discovery and project-ticket writes only to the extent supplied by the current caller. It does not authorize product changes, external environment mutations, repository-history operations, or broader access. If the configured queue is external and the invocation does not carry write authority for it, keep discovery read-only and return ticket-ready records.

Preserve the current checkout, branch, unrelated dirty work, and existing processes. Do not switch or create branches or worktrees, alter history, stash, clean, commit, push, deploy, or modify application behavior.

## Refresh relevant open records

Inspect every open project ticket before searching for new candidates. Recheck its locations, triggering conditions, and claimed mechanisms against the current project tree.

Follow renamed or moved code into current callers and consumers; a missing historical path alone does not prove that a problem disappeared. Add a concise relevance note only when current evidence materially changes an open record. Preserve its identity, evidence history, and lifecycle state. Do not close, reject, split, merge, refine, or reroute tickets in this command.

Use the refreshed open queue for deduplication. A match must concern the same affected behavior and mechanism, not merely similar words or filenames.

## Cover the complete project

Build a temporary coverage map from the project's actual boundaries: manifests, entry points, modules or services, interfaces, data paths, external contracts, and material business areas. Include only what is needed to track the run; do not add a permanent repository map.

Inspect one bounded area at a time using relevant risk directions rather than a generic checklist. Trace cross-component contracts, authority boundaries, state transitions, failure and recovery paths, concurrency, and edge inputs when they are material to that area.

Keep one candidate active at a time. Reconcile or record it completely before pursuing the next candidate, then resume the remaining project coverage. Continue this cycle while project material or a concrete lead remains unexamined.

Use read-only repository and configuration inspection. Do not run project code, tests, builds, linters, servers, containers, migrations, benchmarks, or external systems. Consult current authoritative documentation only when a plausible candidate depends on a changing external contract.

If the execution environment provides delegation and separation would materially improve coverage, assign bounded areas with explicit ownership and evidence requirements. Treat every omission, limitation, or not-covered result as unfinished coverage until it is examined elsewhere or excluded by the project's actual boundaries, capability, or authority. Do not require delegation or assume that a primary-agent interface is available.

## Record defensible candidates

Record a candidate only when both are present:

- a concrete project location or observable behavior;
- a plausible mechanism by which it could produce incorrect behavior, data loss, unsafe access, failed delivery, or another practical regression.

Do not create tickets for preferences, stylistic disagreements, abstract improvements, unsupported speculation, or replacing working technology merely because a newer option exists. Discovery establishes a candidate, not a confirmed cause, complete blast radius, priority, solution, or acceptance criteria.

Before every write, search the configured open queue narrowly for the same problem. Add only material new evidence to a clear match and do not repeat evidence already present. When no clear match exists and writing is authorized, create one observation for one concrete problem using the project's configured ticket format and identity mechanism. Keep uncertain matches separate and note only the possible relationship.

Repeated discovery over unchanged project state and evidence must converge: it must not duplicate records, relevance notes, or evidence. Do not inspect or modify archived or closed records merely to reuse their identity.

## Complete the command

Follow concrete new leads through their relevant callers and consumers and extend the temporary coverage map when they expose an omitted boundary. Finish only after every area in the complete project map is examined or explicitly excluded for a concrete project-boundary, capability, authority, or evidence reason, every defensible candidate is recorded or returned as ticket-ready content, and a final control sweep produces no unprocessed project material or concrete lead.

Do not claim that the project has no remaining defects. Return:

- the exact project inspected;
- the meaningful areas and risk directions covered;
- open-ticket relevance changes, if any;
- tickets created or reconciled, with identities or links;
- ticket-ready records that could not be written and the exact reason;
- remaining unexamined areas and their concrete exclusion or blocker;
- the evidence that no discovered candidate or lead from this run remains unprocessed.
