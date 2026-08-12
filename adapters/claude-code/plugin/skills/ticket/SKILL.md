---
name: ticket
user-invocable: false
description: "Records a concrete problem outside the current definition of done without expanding the active task. Use either when work reveals an incidental observation worth preserving or when an explicitly assigned investigation confirms a problem with evidence. Does not replace unfinished in-scope work, profile scope review, implementation, or independent closure verification."
---

# Ticket

Preserve a concrete out-of-scope problem without silently expanding the current
task. This skill owns ticket intake only. Later profile runs own scope review,
implementation, and independent closure verification.

First identify how the problem reached you:

- If it appeared incidentally while completing another task, read
  [record-observation.md](record-observation.md). Do not investigate it.
- If the immediate caller explicitly assigned investigation of the problem or
  search for new problems, read
  [record-confirmed-problem.md](record-confirmed-problem.md). Confirm it before
  writing it.

Both paths must read [ticket-format.md](ticket-format.md) before creating,
moving, renaming, or updating a ticket.

If the problem prevents achieving or verifying the current definition of done,
it is not out of scope. Handle it through the active workflow instead of using
this skill.
