---
name: mainframe-tickets-find
description: Refresh the relevance of open tickets against the current repository, then search broadly for new concrete problems and record deduplicated observations. Use only for an explicitly requested native Goal discovery run. Do not implement fixes, perform full refinement, or independently close tickets.
---

# Find ticket candidates

Follow the [goal invocation contract](../../commands/workflows.md#goal-plus-ticket-skill).
Load this method afresh even when earlier session context describes ticket work.


Treat the native Goal objective and any plain-language scope supplied with the
explicit invocation as the run boundary. An empty scope means the whole current
repository. Continue until the selected scope is covered, the user pauses or
cancels the run, or no eligible work can continue because of an evidenced
external blocker.

Before writing tickets, read
[ticket-format.md](../mainframe-record-project-problem/references/ticket-format.md).

Apply that reference's legacy-open-ticket normalization before discovery. Do
not ask how to classify an ambiguous legacy record: use the safe canonical
fallback. Keep this as a separate coherent change, and do not count it as a
finding or silently refine ticket claims.

## Refresh the open queue

Before new discovery, inspect every open ticket within the selected repository
scope, regardless of its current queue. With no narrower scope, cover the full
open queue. Recheck the current paths, triggering conditions, and claimed
mechanism against actual code and relevant history. Follow renamed or moved
code into its new callers and consumers; a missing path alone does not prove
the problem disappeared. Prior memory, ticket age, and earlier freshness notes
cannot replace this inspection.

Append a concise relevance note only when evidence materially changes: current
location, changed premise, apparent prior correction, or exact unresolved gap.
Preserve the id, original claim, decisions, implementation evidence, and queue
state. A suspected stale claim is not automatically a verified fix or grounds
for deletion. Keep full confirmation and routing in refine or the appropriate
later workflow, and closure of implemented fixes in verify. Do not create new
statuses or rewrite unchanged tickets just to timestamp a pass.

Use this refreshed queue for deduplication throughout discovery. A match must
share the current failure mechanism, not just old words or filenames. Existing
tickets do not exempt an area from fresh searching. Queue refresh is only the
first part of the goal: it must not replace the subsequent discovery passes.
Keep run-local coverage of checked records and report any unresolved relevance
questions so the next workflow does not mistake old claims for current proof.

## Map the scope

Every new invocation starts a fresh investigation of the current tree, even in
the same session after earlier runs. Memory, previous coverage, and existing
tickets are leads and deduplication aids, never evidence that an area is done.
Reopen the relevant files and trace current behavior. After compaction resume
this run's actual unfinished coverage; do not confuse resumption with a new run.

Build a concise working coverage map from the repository's actual boundaries:
manifests, entry points, modules or services, interfaces, data paths, and major
business areas. Include only enough structure to prove what was inspected. Do
not create a persistent repository map.

Choose relevant risk directions for each area instead of applying one generic
checklist. Process one bounded area at a time. Use a matching specialist only
when specialization or context isolation is worth its briefing and verification
cost.

Every limitation, omission, or `NOT COVERED` result from delegated work is
unfinished coverage until another pass examines it or a concrete reason places
it outside the selected scope or authority. The agent that authored the first
map must not use that map alone as proof that the repository is completely
covered.

## Find and record candidates

Use read-only repository inspection. Do not run project code, tests, builds,
linters, servers, containers, migrations, benchmarks, or external environments.
Consult current owning documentation only when a plausible candidate depends on
a changing external contract; do not turn discovery into full confirmation.

Record a candidate only when both are present:

- a concrete location or observable behavior;
- a plausible mechanism by which it could cause incorrect behavior, data loss,
  unsafe access, failed delivery, or another practical regression.

Do not require proof of cause, actual impact, priority, or full blast radius.
Preferences, abstract improvements, style disagreements, and replacing working
technology merely because something newer exists are not ticket candidates.

Before every write, search the open queue for a clear match. Append only a
materially different observation to that match. Otherwise create a new ticket
under `docs/tickets/open/observations/` through the loaded ticket format. Do not
fix, refine, prioritize, split, consolidate, reject, or move candidates during
this run.

## Preserve the checkout

Work only in the current local checkout and stay on its starting branch. Preserve
unrelated dirty work. Do not create or switch branches or worktrees, or pull,
merge, rebase, reset, cherry-pick, revert, amend, stash, clean, or push. If the
active task authority permits local commits, use coherent
Conventional Commits only as recovery points for ticket records created or updated by this
run.

## Complete the goal

After covering the map, change the search direction: trace cross-component
contracts, failure and recovery paths, authority boundaries, state transitions,
concurrency, and edge inputs where relevant. Follow concrete new leads through
their callers and consumers. Expand the working map when inspection exposes
an omitted boundary. Repeat while a pass produces a new plausible candidate
or an unexplored evidence-backed lead; process both before a further pass.

Finish only after a fresh control sweep across the selected scope produces no
new defensible candidates or unexamined concrete leads, and all coverage gaps
are reconciled. State which different directions were actually inspected and
why remaining hypotheses were discarded or blocked. Ticket counts, a fixed
number of passes, familiar code, prior memory, and declining novelty are never
completion criteria. Do not invent findings to meet a quota or promise that
finite inspection proves the absence of defects.

Do not claim that the repository has no remaining defects. In the final response,
state in plain language:

- the exact scope and coverage completed;
- the normalization performed and any open records safely routed for later
  scope review;
- open-queue relevance coverage and material changed or unresolved premises;
- every remaining unexamined area and the concrete reason it is outside the
  run, or an explicit statement that none remains after reconciling delegated
  limitations;
- how many tickets were created or updated and where;
- what establishes that no discovered candidate remains unprocessed;
- any evidenced blocker that prevented further eligible work.
