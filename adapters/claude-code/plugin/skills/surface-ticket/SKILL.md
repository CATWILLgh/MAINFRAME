---
name: surface-ticket
user-invocable: false
description: "Record a plausible out-of-scope problem without interrupting the current task: search for a similar project ticket, append a materially different observation when one exists, or create a minimal needs-refinement ticket when none exists. Does not investigate root cause, prove impact, assign priority, propose a solution, change lifecycle state, or fix the issue inline."
when_to_use: "Trigger when work reveals a concrete, plausible problem outside the current definition of done and checking it would expand the task. Also use when a new observation may update an existing ticket. Do not use for abstract improvement ideas or for a problem that blocks the current definition of done; the latter belongs to the active task."
---

# Surface ticket

Capture the observation and immediately return to the current task. This skill
is intake only. Later commands own discovery sweeps, refinement, implementation,
and independent closure verification.

## 1. Search for a similar ticket

Search `docs/tickets/` by two or three terms describing the observed behavior,
location, or component. If the directory does not exist, treat the search as
empty. Read only plausible matches far enough to decide whether they describe
the same observed problem.

Do not investigate root cause or blast radius to decide duplication. When the
match is uncertain, prefer updating the closest ticket with the new observation
over starting a parallel record.

## 2. Update or create

When a similar ticket exists, append only information that differs materially:
the new location, symptom, condition, or observed output. Preserve its existing
frontmatter, status, conclusions, and history. Do not reopen, close, approve, or
reprioritize it.

When none exists, read [template.md](template.md) and create one minimal ticket
with status `needs-refinement`. Record what was observed and where. Do not add a
probable cause, impact proof, priority, solution, acceptance criteria, or source
research. A later refinement command owns those decisions.

Use a random eight-character hexadecimal id so independently-created tickets do
not collide. Never rename an existing ticket or replace its history.

## 3. Return to scope

After the ticket write, resume the current definition of done. Do not fix the
finding inline, even if the apparent change is small: its blast radius has not
been established. If the finding prevents achieving or verifying the current
definition of done, stop treating it as out of scope and investigate it through
the active workflow instead.
