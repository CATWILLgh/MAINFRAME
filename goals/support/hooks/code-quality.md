# Report quality regressions introduced by the task

Source: [comment checks](../../../templates/hooks/scripts/comment-discipline-reminder.py), [comment completion check](../../../templates/hooks/scripts/stop-gate-comment-discipline.py), [marker checks](../../../templates/hooks/scripts/scan-suppression-markers.py), [marker completion check](../../../templates/hooks/scripts/stop-gate-suppression-markers.py).

Keep the shared extractors and finding state listed in the [source guide](README.md). Attribute edits and completion events to the same session and writer; preserve the supplied blocking contract where supported.

Purpose: identify changed-code suppressions, deferred implementation, and
temporary process comments without re-reporting untouched repository debt.

`{{HOOK_BINDING}}`: inspect the relevant changed text after edits and, where
supported, recheck unresolved current findings before completion. Keep each
finding attributed to the current task and file change. Comments should explain
durable code reasoning; do not insert ticket history, phase markers, or future
implementation plans as a replacement for finished behavior.

Retain completion blocking for unresolved current findings detected by the
supplied marker and comment rules where the native contract supports it. Do
not add per-finding approvals, allowlists, or file/directory exemptions. A
fixture containing a recognized code comment receives the same treatment as
other supported source. Preserve the extractors' existing distinction between
comments, string data, unsupported file types, and unchanged prior content.
Report what the rule detected, not a claim that it proves semantic
incompleteness. The installer must not invent broader detection rules.

Check in isolation: an introduced real suppression or deferred implementation
is surfaced; an unchanged legacy marker stays quiet; string data is not treated
as a code comment; a fixture has no implicit exemption; resolving the finding clears it; a different task's edit does not
inherit the first task's finding; repeated events remain bounded.
