# Update MAINFRAME

Load the agreed update brief from its explicitly supplied local file or current
conversation. It must identify the chosen source and current product and settle
the choices in [the brief](../prompts/brief.md). If the brief is
missing, ambiguous, or incomplete, do not modify the installation or invent
answers. Explain the missing preparation. Do not repeat the interview or create
a second goal during execution.

Review and update this product's global MAINFRAME installation against the
source agreed during preparation and its current native capabilities. The
pre-goal procedure checks upstream updates and settles whether to incorporate
them before the configuration brief. Do not fetch and adopt newer templates
during this goal. Verify that the checkout still matches the agreed revision
and accepted local changes before writing installation files; changed source
requires reconciliation rather than silent expansion of the approved result.

Your first substantive step is to consult your own current official product
documentation for every relevant layer: global instructions, skills, commands,
hooks, subagents, tool restrictions, settings, and the native goal lifecycle.
Identify the actual product surface and version. Recheck support even if an
earlier installation worked. Do not edit installation files before this pass.

Then follow [the adaptation procedure](support/adapt.md), starting with a fresh copy of
[the progress example](../examples/progress.json), all marks false. Inspect the
whole catalog, including unchanged source items: product changes alone may
justify adapting the installed result. Also inspect previously installed
MAINFRAME material whose source has been removed or renamed.

Reassess the quality of the previous adaptation, even when neither source files
nor installed configuration changed. Current harness capabilities, official
guidance, and the executing model's analysis may reveal a better supported
delivery. Treat previous decisions as evidence to examine, not an untouchable
answer. Revisit earlier unsupported omissions against current capabilities.

Use the model selected by the operator or environment; do not switch models,
change subscriptions, or assume a newer model must produce a better result.
Change a working adaptation only for a concrete improvement in correctness,
compatibility, clarity, or unnecessary instruction load, and verify it. Preserve
user choices and correctly working material when no improvement is established.

Update what needs changing; keep verified correct files as they are. Remove
obsolete MAINFRAME-owned files, duplicate instructions, and stale bindings
after confirming ownership. Preserve user customizations, unrelated
configuration, credentials, and active work. Check
for harmful semantics in the complete effective instruction context.

If an update breaks a previously working hook, restore its backed-up working
implementation and registration, then verify that it still works in the current
environment. Report the failed update and continue independent items. Do not
silently disable the hook or count rollback as successful delivery of the new
version. Follow the rollback boundary in the adaptation procedure.

Complete this single goal when every item is accounted for, obsolete owned
material is reconciled, and the actual result is checked. Report changed paths,
official documentation used, observed checks, unsupported omissions, and any
blocked verification or required reload. Do not create a schedule or background
monitor: the operator runs this goal again when an update is wanted.
