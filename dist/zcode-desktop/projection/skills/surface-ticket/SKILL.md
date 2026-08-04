---
name: surface-ticket
description: Capture any problem you choose not to fix right now — adjacent bug discovered out of scope, in-scope issue you postpone, deliberately deferred refactor, partial implementation, "quick fix" or hack left in place — as a structured ticket in the project's docs/tickets/ folder. Uses a stable template with YAML frontmatter (id/title/status/priority/component/discovered/discovered-from/tags) and a fixed body structure (what observed, why it matters, why not a duplicate, what to do, acceptance criteria, sources). Supports a 5-state audit lifecycle Open / Needs Refinement / In Progress / Closed / Approved with reopen-in-the-same-file when audit fails or when an approved ticket's bug recurs.
when_to_use: Trigger whenever a problem will not be fixed in the current change — an adjacent bug surfaced from another task, an in-scope anti-pattern that cannot be resolved here, a known limitation shipped with the change, a postponed refactor, a partial implementation, a "quick fix" / hack left in place, or a pre-existing failure you did not cause (a red test, broken build, lint or type error already there) — "it was already broken, not mine" is a trigger, not a pass. Also runs on closed-ticket audit cycles and on regressions of previously approved tickets. The act of deciding not to fix now is the trigger; no user acknowledgement required.
---

<!-- Generated from MAINFRAME hub (core/skills/surface-ticket/SKILL.md) — do not edit. -->

# Surface ticket

Persist any problem you choose not to fix right now as a structured ticket in the project's `docs/tickets/`. The companion to the AGENTS.md engineering rules on adjacent-bug surfacing and the suppression-marker ban — the sanctioned outlet for "needs work but not now".

## Discriminator: fix-now vs ticket

The trigger is **the decision to not fix in this change**, not the act of noticing.

- Fixed inline within scope, safely → no ticket.
- Not fixed now (any reason: out of scope, too large, awaits decision, blocked, deferred, partial) → **ticket required before declare-done.**

This makes the rule symmetric with the marker ban in the umbrella AGENTS.md: a TODO/FIXME/`@ts-ignore` in code is forbidden, so the sanctioned alternative is a ticket. The discipline is behavioural (AGENTS.md + this skill), not enforced by a hook.

## When to write a ticket vs fix inline

- **Trivial safe fix** (typo in comment, single variable rename, missing newline — no logic risk): may apply inline. Say so afterwards.
- **Anything else** (logic bug, anti-pattern, missing validation, broken contract, refactor opportunity, scope-creep candidate, known limitation): **ticket, then move on** — the three sources below name where such work comes from.

Three sources of ticket-worthy work — all mandatory before declare-done:

- **Debt you create** — a hack, quick fix, partial implementation, weakened test, or postponed refactor you deliberately leave in the codebase. Surfacing it later is fine; leaving it unwritten is not.
- **Debt you find in your path** — an anti-pattern, missing validation, or design smell in code you are touching but cannot fix here without scope creep. Name it, ticket it, move on — do not silently work around it.
- **Pre-existing failures you did not cause** — a red test, broken build, lint error, type error, or runtime fault that was already there before your change. "It was already broken, not mine" / "my house is on the edge" is **not** a licence to walk past it. You are not obliged to *fix* it (that may be scope creep or risky), but you must *surface* it: ticket it before declare-done. Batch a related cluster — a whole module's red suite, a sweep of one lint rule — into **one** ticket that lists the failures, not one ticket per failing test; a first encounter with a legacy repo can surface dozens, and one-per-failure floods the queue. Two reasons it matters beyond tidiness — a pre-existing red test can mask whether *your* change regressed something, and silent rot is how a codebase decays one "not mine" at a time. If the failure blocks verifying your own change (suite won't run, build is broken), raise `priority` and flag it to the user, not only the ticket.

## Before creating — check for existing

Always search `docs/tickets/` before creating a new ticket. Duplicates fragment context and waste audit cycles.

Search:

```sh
rg -l 'keyword-or-pattern' docs/tickets/
rg -l '^component: <component>' docs/tickets/
```

Use 2-3 distinct keywords that describe the underlying problem, not just the symptom. Cross-check matches by reading frontmatter `title:` and the body's "What was observed" section.

Decision tree on match:

| Existing status | Action |
|---|---|
| `open` / `needs-refinement` / `in-progress` | **Update the existing ticket**, do not create a new one. See [Update an open ticket on re-occurrence](#update-an-open-ticket-on-re-occurrence). |
| `closed` (awaiting audit) | **Update the existing ticket** with a re-occurrence note. This is also a signal for the auditor that the claimed fix may be incomplete. |
| `approved` (finalised, bug recurs) | **Reopen the same file** by default. See [Reopen after approval](#reopen-after-approval-regression). Create a new ticket only if the new occurrence has a clearly distinct root cause. |
| no match | Create a new ticket per the sections below. |

Distinct root cause carve-out — create a new ticket with cross-ref when:
- The recurring symptom comes from a different code path or component than the original.
- The original fix was correct and is still in place; the bug now manifests through a separate underlying mechanism.
- Reopening would force one ticket to track two different root causes, blurring the investigation.

When in doubt, prefer reopen over new — collapsing two unrelated investigations into one ticket is easier to spot and fix later than splitting one investigation across two tickets.

## Setup (first ticket only)

If `docs/tickets/` does not exist in the project yet, create both:

1. `docs/tickets/` folder.
2. `docs/tickets/README.md` with this exact content (kept intentionally short — no per-ticket state here):

```markdown
# Tickets

File-based ticket queue for this project. Convention is managed by the hub `surface-ticket` skill.

- Filename: `<id>-short-slug.md`, where `<id>` is a random 8-hex token (branch-collision-free).
- Status / priority / component live in each ticket's YAML frontmatter, not here.
- List open: `rg -l '^status: open' docs/tickets/`
- High priority: `rg -l '^priority: (critical|high)' docs/tickets/`
- Search body: `rg -l 'keyword' docs/tickets/`
```

## Creating a ticket — read the template first

When you create a ticket, **first read [template.md](template.md)**, then copy its skeleton — do not reconstruct the schema from memory (stale keys and the old sequential-id habit creep back in that way). The template holds the filename rule, the id-generation command, the frontmatter schema, and the body section headers.

What the template enforces, called out here so it is not lost:
- **Filename `<id>-<slug>.md`**, where `<id>` is a **random 8-hex token** (`openssl rand -hex 4`), not a sequential number. Random ids never collide across branches, so there is no renumber-on-merge and no need to scan other branches before allocating. The filename id and the frontmatter `id:` must match.
- **Never omit a frontmatter key.** Empty values are `[]` for lists, `null` / empty string otherwise.
- If the ticket starts as `needs-refinement`, the body may be a one-line stub plus a "Context needed" section; full sections are filled in when status moves to `open`.

## Legacy `NNN-` catalogs

A project that predates the hex convention may hold sequential `NNN-` tickets and a project README that still documents them. The hex rule applies to NEW tickets there too — sequential allocation is what collides across branches and agents, and a large legacy catalog is where the next collision is most likely. So: allocate hex for the new ticket, leave every legacy `NNN-` file untouched (ids are stable), and refresh the stale project `docs/tickets/README.md` to the bootstrap text above so it stops prescribing NNN. A mixed catalog is expected and harmless: order comes from frontmatter `discovered`, not from the filename. Do not renumber old tickets and do not revert to NNN for consistency — a stale local README or the visual pattern of existing files does not override this convention.

## Status lifecycle

| From → To | When |
|---|---|
| create → `open` | Ticket ready for work; all body sections filled |
| create → `needs-refinement` | Stub; context or acceptance criteria not yet developed |
| `needs-refinement` → `open` | Refined into a workable ticket |
| `open` → `in-progress` | An agent took the ticket; another agent should not modify |
| `in-progress` → `closed` | Implementation done; resolution recorded; **awaits independent audit** |
| `closed` → `approved` | Independent auditor verified the diff against the claims |
| `closed` → `open` | Audit failed → reopen the same file. See [Re-audit notes](#re-audit-notes-audit-failed). |
| `approved` → `open` | Regression: bug recurred after the fix was finalised. See [Reopen after approval](#reopen-after-approval-regression). |

**Status changes are made by editing the frontmatter `status:` field, never by renaming or moving the file.** Cross-refs by `id` stay stable.

## Resolution (when moving to `closed`)

Append to the ticket:

```markdown
## Resolution (YYYY-MM-DD)

**Implementer:** <name / role>
**Commits:** <hash1>, <hash2>
**Summary:** <what was done in 2-4 lines>
**Claims to verify on audit:**
- <claim 1, e.g. "0 eslint errors on server/src/dock-slots/">
- <claim 2, e.g. "all 54 tests in slot-blocks.spec.ts green">
- <claim 3, e.g. "build clean on server/">
```

Claims must be testable by the auditor without rerunning the whole task.

## Audit process (`closed` → `approved`)

Run by an **independent agent** (not the implementer). The audit is **real code verification**, not paperwork.

Runbook:

1. Read the ticket fully. List every claim from the Resolution section.
2. Get the diff of cited commits: `git show <hash>` / `git diff <hash>^..<hash>`.
3. **Verify each claim independently:**
   - "0 lint errors" → run the linter against the cited files, compare to 0.
   - "N tests pass" → run the test command, compare count.
   - "build clean" → run the build.
   - "applied in M files" → open each file and confirm it is real, not formal.
4. **Regression scan:** run the full test suite of the affected package. If the implementer did not run it, that itself is a finding.
5. **Diff review for hidden problems:**
   - Suppression markers added without explicit permission (`@ts-ignore`, `eslint-disable`, `.skip` etc.).
   - Tests weakened to pass (loosened assertions).
   - Scope creep — changes outside the ticket scope.
   - Pattern violations vs AGENTS.md (e.g. magic values, hardcoded constants).
6. **Verdict:**
   - All claims hold, no hidden problems → set `status: approved`, append `## Audit (YYYY-MM-DD)` section with summary and auditor name.
   - Problems found → **reopen the same ticket** (see below).

```markdown
## Audit (YYYY-MM-DD)

**Auditor:** <name / role>
**Verdict:** Approved
**Verified:**
- Claim 1 — confirmed: <how>
- Claim 2 — confirmed: <how>
**Regression scan:** <command run, result>
**Notes:** <any minor observations not blocking approval>
```

## Re-audit notes (audit failed)

Triggered when an auditor finds problems in a `closed` ticket and the ticket returns to `open`. **Reopen the same file, do not create a new ticket.** The history of the first attempt and the audit consolidates in one place.

1. Set `status: open` in frontmatter. **Do not touch** `discovered` or the original Resolution section.
2. Append:

```markdown
## Re-audit notes (YYYY-MM-DD)

**Auditor:** <name / role>
**Verdict:** Open (returned to rework)

### Problems found
1. <concrete issue, with file:line or test name>
2. ...

### What to redo
- <concrete fix steps>
```

3. The next implementer adds `## Resolution (second attempt, YYYY-MM-DD)` without deleting the previous Resolution. Cycle repeats until Approved.

## Update an open ticket on re-occurrence

Triggered when the pre-create check finds an already-open ticket (`open` / `needs-refinement` / `in-progress`) or a `closed`-awaiting-audit ticket that covers the same problem you just noticed.

**Do not create a new ticket.** Update the existing one in place:

1. Append to the body:

```markdown
## Re-occurrence noted (YYYY-MM-DD)

**Noticed during:** <task or context where the problem surfaced again>
**Where:** <file:line or component, if different from the original observation>
**Additional details:** <anything new — different symptom, new component affected, narrower reproduction>
```

2. Do not change `status:`, `priority:`, `id:`, `discovered:`, or `discovered-from:`. They reflect the ticket's lifecycle, not the latest sighting.
3. If the re-occurrence raises the impact (e.g. now affecting production traffic), bump `priority:` and note the bump in the appended section.

For a `closed` ticket awaiting audit, this section is also a signal to the auditor that the claimed fix may be incomplete — they should treat the re-occurrence as a finding when verifying the Resolution claims.

## Reopen after approval (regression)

Triggered when a bug recurs after its ticket reached `approved`. **Default: reopen the same file.** The original investigation, fix attempt, audit, and now the regression live in one place — easier to spot incomplete fixes and patterns of recurrence than scattering across multiple files.

1. Set `status: open` in frontmatter. Leave `discovered`, `id`, all prior Resolution and Audit sections untouched.
2. Append:

```markdown
## Reopen (YYYY-MM-DD) — regression after approval

**Originally approved:** <YYYY-MM-DD of the Audit section>
**Recurrence:** <how it manifested again — what was observed, where, when>
**Likely cause:** <best current guess — incomplete original fix, missed code path, regression introduced by later change, environment shift>
**Same root cause as before?** Yes / No / Unclear — see analysis below.

### Analysis
<short reasoning. If "Unclear" or "Yes" — proceed in this file. If "No" → see carve-out below.>

### What to redo
- <concrete next steps for the implementer>
```

3. The next implementer adds `## Resolution (post-regression, YYYY-MM-DD)` without deleting previous Resolution / Audit sections.

**Carve-out — create a new ticket with cross-ref instead of reopening, when:**
- The new occurrence comes from a clearly different code path or component than the original.
- The original fix is still in place and verified; the bug now manifests through a separate underlying mechanism.
- Reopening would force one file to track two distinct root causes, blurring the investigation.

In the carve-out case:
- Create a new ticket per the standard flow.
- Set `discovered-from: ["#<original-id>"]` in frontmatter.
- In the new ticket's "Why it is not a duplicate" section, explain the distinct root cause.
- Add a one-line note to the **approved** original ticket pointing to the new one: `> Related: #<new-id> — distinct root cause, similar symptom.` Do not change the original's status.

When in doubt — reopen. Splitting two distinct causes into separate tickets later is easier than reconstructing two investigations from one merged file.

## Query examples (no central index)

The frontmatter is the source of truth; ripgrep is the navigator.

- All open: `rg -l '^status: open' docs/tickets/`
- All needing audit: `rg -l '^status: closed' docs/tickets/`
- Critical + high: `rg -l '^priority: (critical|high)' docs/tickets/`
- By component: `rg -l '^component: server' docs/tickets/`
- Search body: `rg -l 'pipe validation' docs/tickets/`
- Count by status:
  ```sh
  rg -lo '^status: \w+' docs/tickets/ | sort | uniq -c
  ```

Refresh the project's `docs/tickets/README.md` only if the conventions in this skill change. Per-ticket state never goes there.

## Anti-patterns

- Do not maintain a per-status table in `docs/tickets/README.md` — that hand-maintained index is the pain point this convention exists to avoid (frontmatter + `rg` is the source of truth instead).
- Do not change a ticket's `id` after creation. IDs are stable identifiers.
- Do not rename a ticket file when status changes — frontmatter is the source of truth, file path is the stable cross-reference target.
- Do not silently delete failed audits. Reopen with `## Re-audit notes` so the history is visible.
- Do not create a new ticket without first running the pre-create search. Duplicate tickets fragment context and waste audit cycles.
- Do not create a new ticket for a regression of an `approved` bug when the root cause matches — reopen the original. The carve-out for distinct root cause is the exception, not the default.
- Do not change `discovered:` or `id:` on re-occurrence updates or reopens. They mark the ticket's identity, not the latest sighting.
- Do not silently leave a hack, quick fix, partial implementation, or deferred refactor in the codebase without writing a ticket. The marker ban in AGENTS.md and this skill are a pair — neither works on its own.
- Do not treat a pre-existing failure as out of scope by default. "It was already broken, not mine" is a ticket trigger, not a pass — walking past a red test or broken build without surfacing it is the same omission as leaving your own debt unticketed.
