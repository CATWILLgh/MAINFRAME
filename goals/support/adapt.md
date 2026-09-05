# Adapt the hub to the current environment

This procedure is shared by the install and update goals. It is installation
guidance, not an always-loaded global instruction.

Execute only after [the pre-goal briefing](../brief.md). Follow the configuration
and authority recorded in the agreed brief supplied with the command invocation. Do not reopen
settled preferences. Handle routine adaptation choices independently. A newly
discovered material conflict is a blocker for dependent work: preserve the
affected state, continue independent work, and report the exact unresolved need
without claiming the goal complete or broadening authority.

## Establish the documented contract first

Open the current official documentation for the product and surface you are
using. Discover its documentation index from the publisher; do not substitute
another product's docs, model memory, search snippets, or this hub's examples.
For each relevant layer establish discovery paths, scope, recipients,
precedence, supported fields, permissions, lifecycle events, and reload rules.
Use the product's official model prompting guidance when choosing wording.

Confirm native goal support separately from hooks, task lists, and background
jobs. A similar feature name does not prove identical semantics. If documentation
is inaccessible or a needed contract remains uncertain, leave dependent items
unfinished and report the exact gap. Continue independent documented work.

The installation must use the native surface's real capabilities. Do not build
an adapter directory, compiler, plugin generator, custom goal loop, or telemetry
service in MAINFRAME to compensate for a missing capability.

## Inspect and preserve

Read the checkout's [principles](../../docs/principles.md), catalog, source items,
and their supporting files. Confirm the checkout revision and dirty state.
Use the source revision and local changes agreed in preparation. Do not update
the source checkout mid-goal. If its contents have changed since the brief,
resolve the mismatch before dependent installation writes.
Treat scripts as source to inspect before running; never execute repository
code just to discover whether it is safe.

Discover the actual global destination and existing effective configuration
through documented paths. Inspect only relevant non-secret configuration.
Among supported destinations, use the target product's own configuration or
package root, rather than shared user-wide or system-wide discovery directories.
Global means available across projects in this product; it does not authorize
installing into every product's search path. Do not duplicate payload or add
shared discovery symlinks as a convenience. Use a shared destination only when
no product-specific option is supported and the brief explicitly authorizes that
exception. Otherwise follow the agreed omission or report the unresolved gap;
never invent an unsupported private path. On update, reassess existing shared
placement under this rule. Migrate only owned material within the agreed scope,
verify native loading at the new destination, and preserve other consumers;
prior placement alone does not authorize another shared installation.
Before a write, make a private local backup of the specific affected files,
preserving modes and symlink targets. Do not copy protected credential stores
or expose secrets in diffs, reports, or progress files.

Attribute old material by an existing ownership record, a namespaced dedicated
path, an explicit managed section, or comparison with a known installed source.
A familiar filename alone is insufficient. Preserve user-owned global
instructions, unrelated settings, and user edits. Reconcile MAINFRAME-owned
material around them using the decisions settled in the brief; do not rewrite
the user's instructions or generate a merged replacement without separate
explicit authority. A newly discovered material contradiction leaves dependent
adaptation unfinished; it does not authorize overwriting user content.
Existing approval applies throughout the run; do not request
approval again for ordinary reversible installation work already authorized.

## Keep one disposable checklist

Create a uniquely named local copy of `examples/progress.json` under `.local/`,
outside tracked source. Remember its absolute path in the native goal context.
Each row is one source unit; skills and hooks include their linked scripts,
references, rules, and fixtures. Keep the example itself unchanged. Do not add a lifecycle schema,
event log, evidence store, or a second inventory.

The catalog contains deliverables only. Management prompts, briefing material,
legacy inspection, and adaptation procedures stay in this repository. Never
install them as skills, commands, global instructions, or runtime references.
Keep this run's single agreed objective throughout the catalog.

Read the working copy when resuming after interruption or context compaction.
Set `done: true` only after the unit has been inspected, adapted or deliberately
omitted, and its applicable checks completed. A confirmed unsupported optional
mechanism may be processed with no installation; report that omission. A hook
that cannot be faithfully adapted after the documented compatibility attempt
may also be marked processed as skipped under the agreed fallback. This does
not count as successful activation. For previously working hooks in an update,
apply the recovery policy below instead of using this initial-install fallback.
A failed check, unknown support, missing authority, or pending required reload
leaves `done: false`. A boolean is a progress marker, not proof of correctness.

Use a fresh all-false copy for every new install or update goal. Reuse the same
copy only to resume the same unfinished goal. Add any newly discovered source
units to the current copy; check the actual source tree against the example
before declaring coverage complete. No need to retain the file after completion.

For updates, generate that fresh copy from the catalog at the agreed current
source revision rather than merely resetting a stale checklist that may omit
new units. Inspect removed units through the installation ownership note.
Process the whole set again, including unchanged units and previous omissions:
both native support and the quality of the earlier adaptation may have changed.
Mark each unit only after fresh evaluation and its applicable verification.

## Adapt one unit at a time

Install missing hook dependencies only from the concrete package list and
methods agreed in the pre-goal briefing. Reuse compatible existing tools.
Verify the resolved executable, version, and a small safe/risky fixture before
activating dependent hooks. Record installation ownership in the existing
short local note, including whether a dependency was pre-existing. Do not
replace shared tools, add package managers, or broaden privileges beyond the
agreed scope. Declined dependencies mean their hooks are deliberately omitted.
An approved installation that fails is unresolved work, not a successful skip;
report the failure and continue independent authorized items.

Runtime hook invocations never install or upgrade their own dependencies.

Use the peer-work selection or opt-out settled in the pre-goal briefing. Save
that choice in the existing short ownership note. A missing selection is an
incomplete brief, not a reason to install peers by default. Refresh selected CLI references against their
official documentation. Installing the method does not authorize installing or
upgrading the CLI binaries. A declined optional unit can be marked processed.

Specialist role files are optional starting briefs. Adapt them to native
profiles where useful and supported, or retain them as assignment references.
Do not force delegation or hide skills behind profile membership.

Preserve the source's purpose and acceptance boundary, not its exact wording
or layout. `SKILL.md` frontmatter is an authoring convention, not a guarantee
that this runtime uses it unchanged. Convert metadata, names, paths, references,
and scripts to the documented native form. Preserve supporting resources and
ensure installed links resolve independently of the source directory layout.

Use [the adaptation points](adaptation-points.md) wherever a native
choice adds value. Fill or remove each optional block deliberately. Do not
leave `{{...}}` markers or prose telling a future agent to complete installation
inside delivered instructions or runnable files. Example placeholders intended
for an end user's later project data are separate from installation markers.

Make every skill available to any agent whose task and authority match. Do not
hide methods behind fixed specialist profiles or require a primary session to
execute them. Choose roles dynamically if delegation helps and is available.
Use native tool restrictions when they enforce the assigned boundary; ordinary
prose is not a technical permission control. Without subagents, perform the
method directly and do not claim independent review of your own work.

For hooks, inspect every hook and shared dependency in the supplied source
bundle against its short description in [the hook guide](hooks/README.md).
The bundle's progress mark becomes true only after each applicable hook has
been verified or deliberately omitted; one passing script does not cover it.
Follow the [hook responsibility boundary](hooks/README.md#responsibility-boundary):
adapt native integration, not detection policy. Missing native capabilities
must be reported; do not invent hooks or alternative event lifecycles.
Inspect sibling dependencies and retained reference-protocol assumptions. Adapt
the code using documented native events and payloads; preserve tested detection
logic instead of rebuilding it from prose. Prefer an equivalent existing native mechanism. Apply each hook's
positive, negative, malformed-input, and repetition checks in an isolated
workspace before activation. First try a faithful documented event mapping or
native equivalent. If native capabilities cannot preserve the hook's contract,
skip it, report the attempted mapping and missing coverage, and continue without
another preference question. Do not silently downgrade a guard to a reminder.
An implementation defect or a failed check with unknown cause is unfinished
adaptation, not proof that the harness lacks the capability.

Do not install global network services, paid dependencies, or broaden permissions
without authority for that concrete change. The goal authorizes MAINFRAME
installation, not arbitrary extra infrastructure. Preserve an existing working
credential helper and private index; the shipped index is only an example.

## Inspect semantics and actual delivery

### Recover a failed hook update

Before replacing an installed working hook, verify its current behavior and
back up the owned implementation, dependencies, and registration needed to
restore it. Prefer isolated checks of the new binding before activation.
If the replacement fails, restore that working unit from the backup, preserving
unrelated settings and concurrent user changes. Restore shared MAINFRAME-owned
dependencies and affected bindings together when required for consistency;
do not downgrade shared third-party tools or overwrite user content implicitly.

Verify the restored hook in the current environment. Report the failed update,
rollback result, and actual coverage, and continue independent updates. A
verified rollback retains the old protection but leaves the attempted update
unfinished (`done: false`); do not claim the whole update goal succeeded. Record
a concrete MAINFRAME-caused failure through the harness-feedback route.

If changed native capabilities also prevent the previous version from working,
report that exact blocker and the unverified coverage. Do not claim rollback
restored protection merely because old files were copied back. The ordinary
unsupported-hook skip policy does not authorize silently discarding previously
working protection during an update.

### Check reporting and effective instructions

Establish the cross-project harness-feedback route explicitly. Resolve the
absolute MAINFRAME observation directory and inspect native filesystem and
tool policies, including allow/deny/ask precedence. Configure only the narrowly
authorized reporting access: read open records for deduplication and create or
update observation tickets. This is not permission for unrelated MAINFRAME
changes, publication, protected files, or arbitrary shell execution. Do not
assume an allow rule overrides an explicit deny or the host sandbox.

From a different project, verify path resolution and a harmless temporary
report fixture under equivalent destination permissions, then remove the
fixture. If the actual destination policy cannot be tested without an operator
step, report that exact remaining check. Verify notification to the operator,
or the delegate-to-caller notification handoff. A test entirely inside the
current project does not establish cross-project access. Failed or unavailable
reporting must return ticket-ready text; it must not claim a filed ticket.

Read the effective combination of instructions, selected skills, role briefs,
and hook feedback. Remove semantic duplication, contradictory role ownership,
unnecessary mandatory steps, blanket tool or delegation pressure, repeated
approval demands, and unsupported claims about the environment. Preserve the
user's real safety and product constraints. A keyword match is a review lead,
not proof that an instruction is harmful.

Verify discovery, actual loaded content, resolved links, parsing, permissions,
and documented reload behavior. Use small representative tasks to check skill
selection, direct and delegated use where supported, hook behavior, and the
harness-feedback route. Use a temporary ticket destination for a feedback probe;
do not file a synthetic defect in the real MAINFRAME queue. Keep ordinary
success silent and ensure a repeated event does not produce repeated noise.

An unchanged file still needs the applicable check in an update run. Static
validation cannot prove runtime behavior. If a fresh session or user action is
necessary, report the exact step and keep dependent work unfinished until it
can be verified. Do not equate all checkboxes being true with 100% model quality.

## Defer required reloads until the final verification stage

Complete all independent installation changes and checks that can run without
a reload before asking the operator to restart or open a fresh session. Combine
compatible activation steps into one final handoff instead of restarting after
each unit. If a documented dependency genuinely requires an earlier reload,
finish all other independent work first and explain that specific constraint;
do not claim every product supports a single final restart.

Before the handoff, save the current disposable checklist at its existing
absolute path. Leave items requiring post-reload verification `done: false`.
Write or refresh the ownership and backup note described below before handing
off, so the continuation never depends on a note that has not yet been created.
Provide one concise, copyable continuation instruction containing the agreed
objective and source revision, installed destinations, ownership/backup note
location, checklist path, and exact remaining activation checks. Include the
documented native resume command when available; otherwise provide enough
context to continue in a fresh session without inventing a resume mechanism.
Do not require the previous conversation or create another progress schema.

Tell the operator exactly what needs restarting. Do not interrupt other active
tasks or restart their host implicitly. After continuation, reuse the same
checklist, verify the actual loaded settings and behavior, and finish remaining
items. Do not repeat the brief, reinstall verified units, fetch newer source,
or mark the goal complete before required activation checks pass.

## Leave understandable ownership

Use the native installation mechanism's ownership metadata where it exists.
Otherwise keep one short local note next to the installation with the source
checkout and revision, installed destinations or managed section identifiers,
and the backup location. This is only enough to recognize and recover owned
files during the next update, not another progress system or telemetry log.
Include the already agreed optional-component choices and dependency ownership
in this same note. An update must not infer opt-in from a missing record.

When replacing a legacy install, detach obsolete MAINFRAME registrations before
removing their targets. Inspect symlinks and active runtime dependencies first.
Apply [the model-led legacy inspection method](legacy-audit.md)
to the approved candidates. Do not use a bulk uninstaller, cleanup script, or
name-based deletion rule; inspect and change each owned registration or file
individually, preserving unproven ownership and unrelated consumers.
Preserve unrelated native telemetry and observability preferences. Retire a
legacy MAINFRAME service only with confirmed ownership and authority to stop it.
Do not delete historical data merely because its producer is being removed.

Finish with a concise operator report: actual changes, official source links,
observed checks, unsupported capabilities, and unresolved work. Never expose
credential values or raw transcripts. Report concrete harness faults through
the installed feedback instruction; do not manufacture tickets for normal
unsupported capabilities.

## Verify installed workflow entry points

During installation provide a tested copyable native example for find and
refine. If nested slash commands or skill mentions are not expanded in a goal
argument, use a plain-language objective that explicitly loads the installed
skill by resolved path. Never claim one literal slash syntax works everywhere.
Test a fresh discovery goal in a session containing an earlier exhausted-search
summary: it must inspect the current tree again. Test refinement on a temporary
two-ticket queue: finish the first evidence-and-routing cycle before the second.

Verification: invoke one entry with a bounded harmless scope and check that it
reaches the intended method without duplicate instructions, role reassignment,
scope expansion, or an extra goal. Check that a preparation-only invocation
does not execute the prepared work.

Keep installation probes inside disposable fixtures with an explicit test-only
scope. Never launch discovery or refinement against the operator's real queue
just to prove command binding. When native goals are unsupported, omit runnable
bindings for the Goal-only ticket methods and report that limitation; ordinary
installation prompts do not remove those methods' execution prerequisite.

During updates remove confirmed MAINFRAME-owned general init and management
command bindings. Do not install management prompts or legacy-audit as skills.

## Management is not delivered

Only cataloged materials from `templates/` and the preserved credential helper
are candidates for delivery. `goals/`, `docs/`, `examples/`, and repository
validators are management resources and must not be installed. Hook purpose
and acceptance descriptions under `goals/support/hooks/` guide adaptation but
do not become runtime instructions. Strip authoring and installation guidance
from delivered metadata, roles, settings, and methods. No delivered link may
depend on management resources; rewrite necessary method links to installed
method locations. The MAINFRAME path in harness feedback is a ticket destination,
not permission to load the management workflow automatically.

Before activation check the actual source dependencies: absent Ruff means its
Python security check is unavailable, not a regex substitute. Do not invent
fallback detectors. Existing CLI availability is separate from peer selection;
Gemini CLI is not Antigravity CLI. Use only selected supported peer references.
