---
name: mainframe-record-project-problem
description: Preserve a concrete problem in the receiving project's configured issue queue when work reveals that it will remain unresolved outside the assigned result. Use proactively for evidenced application, data, infrastructure, or project-documentation problems; do not use for unfinished in-scope work, speculative concerns, or faults in MAINFRAME and its agent harness.
---

# Record a project problem

Use this skill when work exposes a concrete problem in the receiving project and resolving it is outside the assigned result. Preserve the finding without silently expanding scope, then continue the assigned work when the problem does not prevent a valid or safe result.

First decide whether the problem belongs to the active work. If it prevents achieving or verifying the assigned result, return it to that work instead of deferring it to a ticket. Do not use a ticket to make unfinished in-scope work appear complete.

When the work will deliberately leave an evidenced problem unresolved, read [references/surface-ticket.md](references/surface-ticket.md) and apply its surfacing boundary before recording or returning the finding.

Do not use this route for a fault in MAINFRAME, its adaptation, hooks, instructions, skills, agents, or effective agent harness. Send that evidence through the configured MAINFRAME harness-feedback route when available; otherwise return the feedback-ready evidence and missing reporting action to your immediate caller.

## Use the project's queue

Locate the issue route already configured for the receiving project. It may be a repository-local queue or an external tracker. Follow its documented ownership, fields, states, and write permissions. Do not write a receiving-project problem into MAINFRAME's own queue, invent a new issue system, or initialize directories merely to record the finding.

If no project issue route is configured, the route is unavailable, or you lack write authority, do not broaden access or claim that a ticket exists. Return a ticket-ready record to your immediate caller and identify the exact missing route, capability, or authorization.

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
