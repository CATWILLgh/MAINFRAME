# Establish a missing local queue

Use only when the current receiving project has no configured issue route and local documentation writes are authorized. Inspect for existing tickets and rule files before creating anything; do not overwrite, migrate, or silently replace them. Existing noncanonical systems belong to the explicit initialization workflow.

Create the lifecycle directories listed below, plus `.campaigns/`. Create `docs/tickets/AGENTS.md` and `README.md` from these blocks. Preserve project-specific ownership and do not alter ignore rules as a side effect. If ownership is unsettled, leave new files uncommitted and surface that choice; recording a finding need not wait for a Git-sharing decision. Do not create fake tickets or empty stage sections.

These templates match the canonical `mainframe-tickets-init` managed blocks; the repository contract checks equality. When changing the schema, update both routes together. After setup, read the created rules, choose a collision-free ID across open and archived records, write the observation and verify its YAML fields, path and evidence. A repeat must reuse the same queue and deduplicate the finding.

## AGENTS.md

```markdown
<!-- MAINFRAME ticket rules: begin -->
# Project ticket system

Ticket schema: mainframe-tickets-v1. This directory stores project issues, not MAINFRAME harness feedback. Read these rules before creating, updating, or moving a ticket.

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

## README.md

```markdown
<!-- MAINFRAME ticket entry: begin -->
# Project tickets

Read [AGENTS.md](AGENTS.md) before working with these tickets. It defines the directories, record format, and lifecycle rules.
<!-- MAINFRAME ticket entry: end -->
```
