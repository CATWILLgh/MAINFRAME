---
name: tickets-find
description: Prepare a goal that searches a repository or named scope broadly for plausible new problems and records deduplicated observations without fixing or confirming them.
argument-hint: "[scope]"
disable-model-invocation: true
---

# Find ticket candidates

Do not start the search in the invocation turn. Return only this copyable block,
with the invocation argument preserved as written:

```text
/goal Follow the loaded tickets-find workflow. Scope: "$ARGUMENTS"; an empty scope means the whole current repository. First normalize current open tickets to the loaded canonical ticket structure without asking the user. Continue until every repository boundary and every limitation or non-coverage reported by delegated work has been accounted for, every concrete plausible finding has been recorded or merged with a clear open-ticket match, and a final control pass leaves no unprocessed findings or unexplained coverage gaps; or stop when the user asks to pause or cancel, or with an evidenced external blocker that prevents any eligible work from continuing. Before finishing, surface the normalization result, checked scope, examined and unexamined coverage, ticket outcomes, and completion evidence in the conversation.
```

When that goal starts, first read
[ticket-autonomous-runs.md](../../references/ticket-autonomous-runs.md),
[record-observation.md](../ticket/record-observation.md), and
[ticket-format.md](../ticket/ticket-format.md).

Build a small coverage map from the repository's actual boundaries, manifests,
entry points, interfaces, and major business areas. Select risk directions that
fit each area instead of applying one generic checklist. Do not create a
persistent repository map during this run.

Before building that map, apply the legacy-open-ticket normalization in
`ticket-format.md`. Do not ask how to classify an ambiguous legacy open record:
use its safe canonical fallback. Do not count normalization as a discovered
problem or silently refine its claims.

Inspect the full repository when the scope argument is empty. A plain-language
argument may narrow the run to a path, component, or concern but grants no new
authority. Record a candidate only when there is a concrete location or
behavior and a plausible mechanism of harm. Do not require proof of cause,
impact, priority, or full blast radius. Preferences, abstract improvements, and
technology replacement merely because something newer exists are not tickets.

Search the open queue for a clear duplicate before every write. Append only a
materially different observation to a clear match; otherwise create a new
`open/observations` ticket. Do not run tests, servers, containers, migrations,
benchmarks, or external environments, and do not fix findings. Continue until
the coverage map and final control pass satisfy the goal condition. Every
limitation, omission, or `NOT COVERED` result from delegated work is unfinished
coverage until a further pass examines it or a concrete reason places it
outside scope or authority. Report remaining unexamined scope explicitly; do
not let an empty first-pass list prove completeness by itself.
