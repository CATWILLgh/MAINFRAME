---
name: mainframe-tickets-find
description: Search the current local repository or a named scope broadly for concrete plausible problems and record deduplicated ticket observations without fixing or fully confirming them. Use only when the user explicitly starts a ticket-discovery run in native Goal mode. Do not use for ordinary incidental findings, focused investigation, implementation, or closure verification.
---

# Find ticket candidates

Treat the native Goal objective and any plain-language scope supplied with the
explicit invocation as the run boundary. An empty scope means the whole current
repository. Continue until the selected scope is covered, the user pauses or
cancels the run, or no eligible work can continue because of an evidenced
external blocker.

Before writing tickets, read
[record-observation.md](../mainframe-ticket/references/record-observation.md)
and [ticket-format.md](../mainframe-ticket/references/ticket-format.md).

Apply that reference's legacy-open-ticket normalization before discovery. Do
not ask how to classify an ambiguous legacy record: use the safe canonical
fallback. Keep this as a separate coherent change, and do not count it as a
finding or silently refine ticket claims.

## Map the scope

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
active primary-session authority permits local commits, use coherent
Conventional Commits only as recovery points for ticket records created by this
run.

## Complete the goal

After covering the map, perform one control pass for unprocessed findings. The
run is complete when every mapped area was inspected along its relevant risk
directions and every concrete plausible finding was recorded, merged with a
clear open-ticket match, or discarded for a stated non-ticket reason.

Do not claim that the repository has no remaining defects. In the final response,
state in plain language:

- the exact scope and coverage completed;
- the normalization performed and any open records safely routed for later
  scope review;
- every remaining unexamined area and the concrete reason it is outside the
  run, or an explicit statement that none remains after reconciling delegated
  limitations;
- how many tickets were created or updated and where;
- what establishes that no discovered candidate remains unprocessed;
- any evidenced blocker that prevented further eligible work.
