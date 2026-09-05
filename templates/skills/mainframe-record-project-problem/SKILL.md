---
name: mainframe-record-project-problem
description: Record a concrete repository problem that remains unresolved because it is outside the active task's assigned result. Use when work exposes a defect, limitation, or required follow-up that the current task will not resolve. Create one minimal record and return to the assigned work; do not defer unfinished in-scope work.
---

# Record a project problem

Preserve a concrete problem outside the active task without silently expanding
scope. Write one new record from the evidence already available, then return to
the assigned work. Do not search for an existing ticket, merge observations,
or update another ticket; the later ticket-refinement workflow owns
deduplication and consolidation for incidental observations. An explicitly
active `mainframe-tickets-find` or harness-feedback workflow owns its different
deduplication rules; follow that workflow directly instead of applying this
incidental-recording rule to it.

Choose one path before writing:

- For an incidental finding outside an active discovery workflow, read
  [record-observation.md](references/record-observation.md). Do not investigate
  beyond the evidence needed to describe the observation.
- For a focused investigation or confirmation explicitly assigned by the
  immediate caller, read
  [record-confirmed-problem.md](references/record-confirmed-problem.md). Confirm
  the problem before writing it.

Read [ticket-format.md](references/ticket-format.md) before creating a ticket.

If the problem prevents achieving or verifying the active result or agreed
definition of done, it is in scope. Return it to the active workflow instead of
recording it as an external ticket.
