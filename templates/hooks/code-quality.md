# Report quality regressions introduced by the task

Purpose: identify changed-code suppressions, deferred implementation, and
temporary process comments without re-reporting untouched repository debt.

`{{HOOK_BINDING}}`: inspect the relevant changed text after edits and, where
supported, recheck unresolved current findings before completion. Keep each
finding attributed to the current task and file change. Comments should explain
durable code reasoning; do not insert ticket history, phase markers, or future
implementation plans as a replacement for finished behavior.

Treat suppression markers and placeholder-like text as inspection candidates.
Fixtures, documentation examples, established generated files, and deliberate
authorized exceptions are not automatically defects. Block completion only for
a confirmed unresolved current violation when the native contract supports it.
Use advisory feedback for uncertain semantics. Do not add keyword-only gates
that claim to judge whether code is complete.

Check in isolation: an introduced real suppression or deferred implementation
is surfaced; an unchanged legacy marker stays quiet; an intentional fixture is
not blocked; resolving the finding clears it; a different task's edit does not
inherit the first task's finding; repeated events remain bounded.
