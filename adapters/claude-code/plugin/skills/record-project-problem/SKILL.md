---
name: record-project-problem
user-invocable: false
description: "Records a concrete repository problem that remains unresolved because it is outside the active task's assigned result. Use when work exposes a defect, limitation, or required follow-up that the current task will not resolve. Creates one minimal record and returns to the assigned work; does not defer unfinished in-scope work."
---

# Record a project problem

Preserve a concrete problem outside the active task's assigned result or agreed
definition of done without silently expanding scope. Write one new record from
the evidence already available, then return to the assigned work. Do not search
for an existing ticket, merge observations, or update another ticket; the
later ticket-refinement workflow owns deduplication and consolidation.

First identify how the problem reached you:

- If it appeared incidentally while completing another task, or a broad
  discovery run found it as a plausible candidate, read
  [record-observation.md](record-observation.md). Do not investigate beyond the
  evidence needed to describe the observation.
- If the immediate caller explicitly assigned confirmation or focused
  investigation of the problem, read
  [record-confirmed-problem.md](record-confirmed-problem.md). Confirm it before
  writing it.

Both paths must read [ticket-format.md](ticket-format.md) before creating a
ticket.

If the problem prevents achieving or verifying the assigned result or agreed
definition of done, it is not out of scope. Handle it through the active
workflow instead of using this skill.
