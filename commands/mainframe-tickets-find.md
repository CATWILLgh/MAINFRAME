# Investigate random project areas and record proven problems

This is a user-invocable command. Execute it only because the current invocation explicitly selected it. It takes no arguments and operates on the current project. When combined with a native goal, continue the campaign under that goal until the stopping criterion below is met or the user stops it. This command alone does not create a goal or background automation.

Repeatedly choose a random project area, investigate it, immediately persist a supported problem or consolidate new evidence into its existing ticket, then choose another area. Do not implement fixes, assign priorities, decide unresolved product behavior, or advance tickets through later lifecycle stages.

## Read the initialized ticket contract

Read `docs/tickets/AGENTS.md` and check its directory, record-format, and lifecycle rules before queue writes. If the root, contract, or required layout is missing or conflicts with effective project rules, report that `mainframe-tickets-init` must initialize or reconcile it; do not run initialization implicitly, invent another tracker, or migrate unrelated records. Use `docs/tickets/` in the current project only. The directory is state: do not add a YAML `status` field. Preserve string IDs, required frontmatter, meaningful evidence and links. Exclude `.campaigns/` and `.migration/` from every ticket scan.

Read only relevant matches across the five `docs/tickets/open/` queues for deduplication. Create new records in `open/observations/` with `id`, `title`, `component`, `created`, `created-from` and an `Evidence` section. New IDs are quoted four-character lowercase hexadecimal strings checked against open and archived IDs; retain existing IDs. Add new facts to matching open records without changing their lifecycle or execution marker. Record trigger/location, actual and expected behavior with sources, consequence, and uncertainty. Keep this campaign's random-point history and duplicate streak under `.campaigns/`; never count state files, migration snapshots, or terminal records as open duplicates.

## Resolve project storage and authority

Use the initialized project contract for ticket identity, fields, destinations and `.campaigns/` storage. Follow its template and validate required fields, Markdown structure and links before saving. Preserve existing tracked or ignored ownership; campaign state is not a defect ticket or durable project skill.

The invocation authorizes project investigation and local ticket and campaign-state writes within the effective project policy. External ticket writes and access to shared or remote environments require the applicable caller authority. Preserve unrelated work and processes. Do not change application behavior, switch branches, alter history, commit, push, deploy, or broaden access during this command.

## Choose and investigate one random point

Build a lightweight candidate pool from the actual project structure: modules, entrypoints, user scenarios, interfaces, data paths, and cross-component contracts. Randomly sample or shuffle it using an available local mechanism. Expand the pool as investigation reveals other boundaries. Do not select points from existing tickets to manufacture duplicate matches, repeatedly inspect one known defect, or claim randomness for a fixed favorite checklist.

Keep one point active through investigation and recording. Avoid revisiting the same point within the current selection cycle; after exhausting the pool, vary the scenario, contract, inputs, or failure condition and continue. A point with no defect is not proof that its module or project is defect-free. An exhausted pool or an elapsed work period is not a completion criterion.

Trace relevant callers, consumers, state transitions, failure paths, and real project requirements. Use current authoritative internet sources and available MCP resources when they can establish the applicable behavior, compatibility, or intended contract. Match external evidence to the project's actual versions and environment. Cite the specific source and what it establishes; search snippets, stale documentation, and model confidence are not proof. Do not transmit secrets or private project material to external sources.

Use the smallest safe inspection, local test, reproduction, or measurement that can settle the suspected problem. Check side effects before running project commands and use disposable fixtures only within existing authority. Available credentials, tools, or localhost addresses do not authorize remote access or disposal. A blocked source or unavailable check leaves that claim unresolved; continue other available investigation without inventing evidence.

## Establish a real problem and deduplicate

Record only a problem supported by current evidence: an affected project location or behavior, its triggering conditions, the expected behavior and its basis, and a demonstrated discrepancy or concrete defect established by inspection. Include practical consequences and distinguish what is proved from remaining uncertainty. A reproducible execution is useful but not mandatory when source inspection proves the defect.

An optimization qualifies when evidence establishes a meaningful avoidable cost or constraint violation. Do not create tickets for stylistic preferences, speculative mechanisms, newer technology alone, or guessed business requirements. Full root cause, complete blast radius, priority, and implementation design belong to later stages when not yet established.

Before every write, search the configured open queue for the same behavior, mechanism, and affected boundary. Read relevant matches rather than re-auditing every open ticket. Follow moved code when needed; keywords or an old path alone do not establish identity.

- No matching record: create one ticket using the configured identity, initial lifecycle state, YAML and Markdown requirements.
- A matching record with substantial new evidence: consolidate that evidence into its relevant sections, correcting stale conclusions while preserving identity and useful history. Do not append a repeated investigation diary or change the lifecycle state.
- A matching record with no substantial new evidence: leave it unchanged and continue.

Preserve sources, conditions, observed and expected behavior, and important unknowns in the ticket itself so another session can continue without this conversation. Save and confirm each ticket update before moving to the next point. If a write is unavailable, retain ticket-ready evidence in permitted campaign state and report the exact missing action; do not claim persistence or successful campaign completion.

Do not mutate closed or archived records. If a matching terminal record is encountered, verify whether this is a recurrence; a present recurrence needs a new linked observation under the project's rules and does not count as an already-covered open problem.

## Preserve campaign continuity and count saturation

Save concise campaign state after each point: campaign identity, relevant project revision or dirty-state boundary, point and selection history, evidence outcome, ticket identity, unresolved evidence or writes, and the current consecutive-duplicate count. Preserve enough history to avoid counting a repeated inspection as a new random point. Resume that same campaign after context changes; do not reset progress merely because a new turn or session began. Revalidate affected evidence and reset an unsupported streak when relevant project changes invalidate it.

The completion threshold is **10 consecutive investigations of distinct randomly selected points**, each establishing a real problem already covered by an open ticket, with no substantial new evidence to add.

- An established duplicate with no new evidence increments the count once for that point, regardless of how many matching tickets exist.
- A new problem or substantial addition to an existing ticket resets the count to zero.
- A point with no established problem, an inconclusive investigation, a repeated point, or unavailable evidence does not qualify and breaks the consecutive streak.
- Tool calls, retries, context changes, or replaying a saved result do not create additional attempts.

Never skip a new finding to preserve the streak. If several problems emerge from one investigation, reconcile all of them before choosing another point; any new problem or material evidence resets the streak.

## Continue or report the stopping result

Continue while the count is below 10 and authorized investigation remains possible. Do not finish a goal because the code seems clean, all mapped areas were visited, no problem was found in a short period, or the agent believes it has checked everything. Finite native execution or budget limits remain binding; preserve a continuation state rather than label interrupted work complete.

A user stop ends the campaign as requested. If no authorized progress remains possible, report the concrete blocker and preserve resumable state; a blocker is not successful completion. Follow the native goal's actual status rules without substituting a completion claim.

At 10 qualifying consecutive duplicates, verify the saved evidence and that no discovered finding or write remains unprocessed. Report completion by the agreed duplicate-saturation criterion, never absence of defects. Return created or materially updated ticket links, the saved campaign-state location, the streak and its supporting ticket identities, and material unresolved limitations. For an interrupted campaign, report its continuation point instead. Omit empty categories.
