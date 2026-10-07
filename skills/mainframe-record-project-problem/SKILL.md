---
name: mainframe-record-project-problem
description: Preserve unresolved project findings as structured tickets during ordinary work; establish a local ticket queue when none exists. Not an audit campaign or a way to defer unfinished work.
---

# Record a project problem

Operate in the current project: the repository named by the task or, absent that, the active working repository. An explicit request to use this skill means apply the recording method there. Keep discovery and ticket writes inside that project and its explicitly configured issue routes.

Use this skill when work exposes a concrete problem in the receiving project and resolving it is outside the assigned result. Preserve the finding without silently expanding scope, then continue the assigned work when the problem does not prevent a valid or safe result.

First decide whether the problem belongs to the active work. If it prevents achieving or verifying the assigned result, return it to that work instead of deferring it to a ticket. Do not use a ticket to make unfinished in-scope work appear complete.

When the work will deliberately leave an evidenced problem unresolved, read [references/surface-ticket.md](references/surface-ticket.md) and apply its surfacing boundary before recording or returning the finding.

If no concrete project finding exists yet, keep this method ready for the assigned work; do not fabricate tickets or start a random search campaign.

## Use the project's queue

When the project uses `docs/tickets/AGENTS.md`, read that contract and create observations with its required YAML fields and Evidence section. Preserve matching open records; recording does not perform campaign investigation or lifecycle transitions.

Otherwise inspect only the current project's effective instructions and configured issue locations. Honor an established local queue or external tracker; do not establish a competing source of truth. Existing noncanonical tickets require the explicit `mainframe-tickets-init` migration workflow, not silent normalization by this skill.

If no issue route exists and local documentation writes are authorized, establish `docs/tickets/` using [references/new-queue.md](references/new-queue.md), then record the evidenced finding in `open/observations/`. An explicit request to apply this skill authorizes this local setup unless the task or project forbids it; automatic use stays within existing write authority. Create the rule files and directories, not an audit campaign or artificial records. Preserve the project's tracked/ignored ownership and do not change ignore rules without a settled choice.

If the configured route is unavailable or write authority is absent, return a ticket-ready record with the exact missing capability or authority. Do not substitute another repository's queue for the project's queue.

Creating or changing an external issue is an external mutation. Perform it only when the assigned authority includes that action.

## Preserve the evidence level

Use only evidence already produced by the assigned work. You may inspect the immediate location or output needed to identify the observation accurately, but do not start a separate root-cause, impact, priority, or blast-radius investigation unless it was assigned.

Record:

- a concise factual title;
- the affected project location or component;
- the observed behavior and the action or condition that exposed it;
- direct evidence available from the current work;
- required or expected behavior only when a project source or assigned requirement defines it;
- relevant uncertainty and what has not been established;
- the active work during which it was found and why resolution remains outside its result.

Do not invent a cause, severity, business impact, proposed solution, acceptance criteria, or certainty stronger than the evidence. Keep secrets, protected data, raw transcripts, and unrelated diagnostic output out of the record.

## Reconcile instead of duplicating

Before creating a record, search the configured open-project queue narrowly for the same concrete problem. Treat shared keywords alone as insufficient; compare the affected behavior, location, and evidence.

- If a clear open match exists, add only material new evidence permitted by the queue and preserve its existing identity and history.
- If no clear match exists, create one record for one concrete problem using the queue's native identity mechanism.
- If the match remains uncertain, do not merge unrelated findings. Create a distinct record when authorized and note the possible relationship without claiming duplication.

Repeating the same recording operation with the same evidence must converge on one effective open record and must not append the same evidence twice. Never alter an archived or closed record merely to reuse its identity; follow the configured project lifecycle for a recurrence.

After recording, return the record identity or link and state whether it was created or reconciled. If no write occurred, return the ticket-ready content and the exact next action instead.
