---
name: tickets-refine
description: Prepare a goal that verifies, scopes, splits, and consolidates open ticket observations, routing each result to technical work, a user decision, or rejection.
argument-hint: "[scope]"
disable-model-invocation: true
---

# Refine open tickets

Do not start refinement in the invocation turn. Return only this copyable block,
with the invocation argument preserved as written:

```text
/goal Follow the loaded tickets-refine workflow. Scope: "$ARGUMENTS"; an empty scope means every eligible ticket in open/observations and open/needs-scope-review. Continue one ticket at a time until every eligible ticket has been verified, atomized, checked for meaningful duplicates, scoped across its known blast radius, and moved to ready, needs-decision, or archive/rejected; or stop with an evidenced external blocker that prevents any eligible work from continuing. Before finishing, surface the checked queue, ticket outcomes, unresolved decision boundaries, and completion evidence in the conversation.
```

When that goal starts, first read
[ticket-autonomous-runs.md](../../references/ticket-autonomous-runs.md) and
[ticket-format.md](../ticket/ticket-format.md).

Work from `open/observations` and `open/needs-scope-review`. A plain-language
argument may narrow the queue by ticket id, path, component, or concern but
grants no new authority. For each ticket:

1. Restate a falsifiable problem and verify it against current repository
   evidence and, where relevant, current authoritative external contracts.
2. Find affected locations and meaningful consequences far enough to establish
   the blast radius. Separate independent problems into separate tickets while
   preserving the original history and links.
3. Compare plausible semantic duplicates, not only matching words. Keep the
   clearest canonical open ticket; update it with material evidence, then move
   confirmed duplicates to `archive/rejected` with a link and reason.
4. Move a disproved or superseded ticket to `archive/rejected`; move a fully
   scoped technical problem needing no user choice to `ready`; move a genuine
   product, business-logic, material infrastructure, destructive-action, or
   authority choice to `needs-decision` with the exact decision stated plainly.

Do not run tests, servers, containers, migrations, benchmarks, or external
environments, and do not implement a fix. Existing tests and saved outputs may
be read as evidence. Do not invent certainty when a claim requires a new
measurement: preserve the missing evidence and route the ticket according to
the actual decision boundary rather than guessing.
