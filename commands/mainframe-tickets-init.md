# Initialize or normalize the project's ticket system

This is an explicit user-invoked, no-argument command for the current project. Establish `docs/tickets/` and migrate existing project tickets into the standard below. Do not investigate ticket claims, deduplicate problems, implement fixes, or infer user approval. Run only for the current project under an explicit initialization request.

## Resolve and preserve existing ownership

Resolve the current project and inspect its effective instructions and existing ticket locations, schemas, links, and tracked/ignored ownership. Confine discovery to that project and explicitly configured issue routes. Preserve unrelated documents, code, dirty work, and user configuration. Reuse the project's established ownership for ticket files; if no evidence decides whether new records should be shared through Git or remain local, resolve that one choice before changing ignore rules.

The invocation authorizes local ticket migration and ticket-rule files. An external tracker is not a local directory to move: use an already authorized export when available, preserve external identities and URLs, and do not mutate the service or establish a competing live queue without an explicit source-of-truth decision. Report such a boundary instead of pretending initialization succeeded.

Inventory records and proposed old-to-new paths before moving them. Identify semantic state from explicit metadata and history, not folder spelling alone. Preserve existing IDs, body content, meaningful history, evidence, and relationships. Assign new four-character lowercase hexadecimal IDs only to records without an ID, checking all active and archived IDs for collisions. Quote IDs in YAML, including numeric-only IDs. Never overwrite records or silently regenerate conflicting existing IDs; resolve an ambiguous identity before migrating the affected records.

## Map records conservatively

Map each existing record to one destination:

| Evidence already in the record | Destination |
| --- | --- |
| New finding with no completed investigation | `open/observations/` |
| Unclear open state, missing investigation, or unsupported readiness | `open/needs-scope-review/` |
| A specific unresolved user-owned decision or authority requirement | `open/needs-decision/` |
| Completed investigation, fixed expected behavior and explicit autonomous boundary | `open/ready/`, `execution: autonomous` |
| Completed investigation plus recorded user approval for one bounded implementation | `open/ready/`, `execution: user-approved` |
| Completed implementation with evidence awaiting an independent check | `open/needs-verification/`, preserve its evidenced execution route |
| Existing explicit terminal resolution | `archive/resolved/` |
| Existing explicit rejection, supersession, or duplicate outcome | `archive/rejected/` |

Do not turn a historical closed label into a claim of newly performed independent verification. Preserve its recorded basis and any missing evidence as legacy uncertainty. Do not fabricate an execution route for a legacy implemented record: retain its evidence and route it to `needs-scope-review` to recover the missing boundary. Ambiguous terminal-vs-open status requires resolution, not an invented closure.

This command alone may normalize legacy terminal paths and metadata during migration. Preserve their original bodies and prior metadata in a recoverable snapshot first. After normalization, all working commands treat terminal records as immutable. Existing canonical terminal records need no rewrite. Migration does not reopen a terminal issue; a later recurrence receives its own linked ticket.

## Apply a recoverable, convergent migration

For a migration, save a project-local recovery snapshot and mapping under `docs/tickets/.migration/` before editing existing ticket files. Keep it outside queue discovery. Include original bytes, relevant file modes, identities, old/new paths, and completion markers; never copy credentials or unrelated files. Preserve unresolved material in place and mark initialization incomplete until its mapping is settled. Resume an interrupted migration from its mapping and actual files rather than overwriting destinations or creating duplicates.

Create the seven lifecycle directories in the template and `.campaigns/` for find/refine/implement continuation records. Normalize each ticket's frontmatter and body without discarding legacy information. Add missing fields only from existing facts; use `unknown` for unavailable origin/component/date facts rather than inventing them. Preserve additional meaningful fields except a legacy `status`: preserve its original value in migration evidence, remove it from effective frontmatter, and let the destination directory own state.

Use `<id>-<descriptive-kebab-case-slug>.md`, preserving valid existing IDs. Move one record at a time, verify the destination, and update mutable project-local ticket links and inbound documentation links to moved records without changing unrelated prose. Remove an old path only after the verified destination and recovery mapping exist. Do not rewrite external links, code, or unrelated project configuration. A repeated run over a canonical system must make no content changes or extra snapshots.

## Install the ticket-root instructions

Create or reconcile `docs/tickets/AGENTS.md` from the exact managed block below. Preserve existing project-specific material outside the block. If existing instructions contradict the standard, resolve the concrete conflict instead of stacking incompatible rules. The README's managed section directs readers to AGENTS.md; preserve unrelated user content outside it. Working commands explicitly read this file even where the product does not automatically load nested AGENTS.md.

AGENTS.md managed block:

```markdown
<!-- MAINFRAME ticket rules: begin -->
# Project ticket system

This directory stores issues in the current project. Read these rules before creating, updating, or moving a ticket.

## Directories own lifecycle state

- `open/observations/`: new supported findings awaiting deep investigation.
- `open/needs-scope-review/`: missing investigation, uncertain relevance, execution route, affected scope, or evidence.
- `open/needs-decision/`: a specific user-owned product, data, infrastructure, or authority decision is required.
- `open/ready/`: investigated work with fixed requirements and a recorded execution route.
- `open/needs-verification/`: completed implementation awaiting independent verification.
- `archive/resolved/`: a verified correction, or a preserved explicitly identified legacy resolution.
- `archive/rejected/`: an evidenced rejection, supersession, or confirmed duplicate.

There is no `in-progress` directory and no YAML `status` field. A ticket stays in its current queue while that stage works on it. Change the directory only when the stage has evidence for its next state. Preserve one live record per ID and update links in writable open tickets after a move. Historical links inside immutable archived records remain unchanged; resolve them by their preserved ID and migration mapping when needed. Links from non-ticket files are outside working-command write authority: report them for an authorized update. Do not treat a move as evidence by itself.

## Identity and record format

Use `<id>-<short-kebab-case-slug>.md`. New IDs are random four-character lowercase hexadecimal strings, unique across open and archived tickets. Preserve legacy IDs and every ID throughout its lifetime. Quote the YAML `id` so numeric-only or legacy IDs remain strings.

Every record has YAML frontmatter: `id`, `title`, `component`, `created` (YYYY-MM-DD or `unknown` for unrecoverable legacy dates), and `created-from`. Use verified facts; retain meaningful legacy fields and history. Ready and verification records also require `execution: autonomous` or `execution: user-approved`.

`autonomous` requires an `## Autonomous implementation boundary` section stating the fixed expected behavior, its evidence, and decisions excluded from the change. `user-approved` requires an `## User decision` section recording the actual decision, authority and bounded acceptance conditions. Autonomous queue implementation selects only `execution: autonomous`; it never consumes user-approved work without an explicit assignment for that ticket. Neither marker grants deployment, remote writes, or push authority.

The Markdown body starts with the title and an `## Evidence` section: trigger, affected location, actual and expected behavior with their sources, practical consequence, and remaining uncertainty. Add only stage-relevant sections:

- `## Investigation`: code trace, cause or demonstrated mechanism, alternative explanations, blast radius and evidence limits.
- `## Acceptance`: observable conditions that implementation and verification must establish.
- `## Relationships`: primary/duplicate, related, split-from or recurrence links and reasons, when applicable.
- `## User decision`: a precise unresolved question and viable choices, followed by actual agreement when obtained.
- `## Implementation`: changed locations, pre-change evidence, checks and results, limitations and checkpoint references.
- `## Verification`: independence basis, current evidence, verdict, adjacent risks and unobserved boundaries.
- `## Blocker`: exact unavailable evidence, environment or authority and the condition for resuming, when applicable.

Do not create empty sections or copy raw logs. Consolidate new evidence in its owning section while preserving useful historical observations and decisions. Link specific current authoritative external sources and applicable versions when they establish a contract. Never manufacture cause, priority, authorization, or certainty.

## Responsibilities and transitions

- `mainframe-tickets-init` owns schema initialization and legacy normalization. Other commands do not migrate the whole queue.
- `mainframe-tickets-find` creates observations or adds material evidence to matching open records, preserving their current state.
- `mainframe-tickets-refine` investigates observations and scope-review records. It routes to ready, needs-decision, needs-scope-review, or archive/rejected based on evidence, and consolidates confirmed duplicates before retiring secondary records.
- `mainframe-tickets-implement` processes autonomous ready records, recording implementation and verification evidence, then moves them to needs-verification. A misclassified record returns to scope review or a user decision; a disproved or duplicate claim may be rejected with evidence. Local verified commits follow the command and project authority.
- `mainframe-tickets-verify` independently checks needs-verification records. It moves a proved correction to archive/resolved, failed implementation to ready, missed scope to needs-scope-review, user-owned choices to needs-decision, and disproved or duplicate claims to archive/rejected. An unavailable check may leave the ticket awaiting verification with an exact blocker. Its only persistent project edits are ticket records.

A ticket awaiting a user decision is not autonomous work. An explicitly assigned decision-handling conversation records the actual agreement and its scope. It moves fully investigated work to ready with `execution: user-approved`, or to needs-scope-review if investigation remains incomplete. Refinement preserves this execution route; it must not silently convert the ticket to autonomous queue work. Approval for an already implemented but blocked check returns that ticket to needs-verification once prerequisites exist; it does not imply another implementation or a passing check.

All campaigns process one ticket or finding at a time. Deduplicate by demonstrated behavior and mechanism, not title similarity. Keep related independently fixable problems separate. Terminal records are immutable outside explicit legacy initialization; a recurrence gets a new ID and a link. Search archived IDs to prevent collisions without treating archives as an active queue.

`.campaigns/` holds find/refine/implement continuation state, not defect records. Verification progress stays in its tickets and existing native goal state. `.migration/` holds recovery material, not active evidence or instructions. Exclude both from queue scans and duplicate counts. No command invokes another workflow merely because it is named here.
<!-- MAINFRAME ticket rules: end -->
```

README.md managed block:

```markdown
<!-- MAINFRAME ticket entry: begin -->
# Project tickets

Read [AGENTS.md](AGENTS.md) before working with these tickets. It defines the directories, record format, and lifecycle rules.
<!-- MAINFRAME ticket entry: end -->
```

New observation template; substitute facts and do not leave placeholders:

```markdown
---
id: "<new-id>"
title: "<problem>"
component: "<component>"
created: <YYYY-MM-DD>
created-from: "<task or investigation>"
---
# <problem>

## Evidence

- Trigger and location: <specific conditions and source link>
- Actual behavior: <supported observation or demonstrated defect>
- Expected behavior: <requirement and source>
- Consequence: <supported impact>
- Uncertainty: <material unknowns, or none>
```

## Verify initialization

Check every migrated or created record for valid YAML, string identity, required facts, correct filename and lifecycle directory, execution-route requirements, preserved evidence, and resolved links in changed records. Report preserved historical links in untouched terminal records separately; do not rewrite immutable history solely to refresh a path. Verify counts and ID mappings against the pre-migration inventory so no record is lost, overwritten, or accidentally duplicated. Ensure snapshots and campaign files cannot be selected as tickets.

Confirm a new observation, an autonomous ready record, and an implemented record have unambiguous next commands from the installed rules; use synthetic in-memory examples rather than creating fake project issues. Check that a second reconciliation would be a no-op. Report the root, initialized or migrated record counts, preserved legacy exceptions, recovery location when used, and any precise unresolved mapping or ownership. Do not declare initialization complete while records still violate the contract or meaningful evidence was lost.
