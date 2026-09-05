---
name: mainframe-harness-feedback
description: Record an observed harness fault and notify the operator, including noisy hooks, false blocking, instruction conflicts, or lost context. Do not use for application defects or routine successful checks.
---

# Report a harness problem

Use the observation already available. Capture the component, triggering action,
observed behavior, expected behavior when known, practical consequence, and a
short redacted example. Distinguish an observation from a reproduced cause.
Do not search transcripts, protected stores, or unrelated projects for more
material, and do not start background telemetry.

Resolve `{{MAINFRAME_ROOT}}/docs/tickets/open/observations/`.

Use this absolute MAINFRAME destination even when the active task is in another
repository; do not create a MAINFRAME defect ticket in that project's queue.
Use the configured reporting route within its actual permissions. Hook output is evidence for a report,
not evidence that a ticket has already been written.

Follow the existing local ticket convention. If none exists, create a concise Markdown ticket with
a unique filename and the fields above. Search only open tickets for a clear
match; update that match with material new evidence instead of creating one
report per repeated hook message. Keep archived tickets unchanged.

Notify the operator once with the practical impact and ticket link. If acting
as a delegate without direct operator communication, return the link and an
explicit request for the caller to notify them. If writing outside the assigned
scope is forbidden or the checkout is unavailable, return ticket-ready text and
the missing write/notification step; do not broaden access or claim it was filed.

Continue the authorized task when possible. Fix the harness only when that is
within the assignment. Do not disable a safety guard just to avoid its refusal.
For a feedback-route test, use a temporary ticket directory and a synthetic
observation explicitly labeled as a probe; do not create a real defect ticket.
