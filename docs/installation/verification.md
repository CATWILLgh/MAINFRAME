# Verification

Delivery and verification are separate. A lower verification layer never proves
a higher one, but missing native behavior proof does not erase a completed file
delivery. Schema 2 records these dimensions independently:

- `delivery` is `pending`, `installed`, or `unsupported`;
- `verification` is `pending` or `passed` for delivered or still-pending
  components, and is omitted when delivery is `unsupported`;
- `reason` records only an actual product limitation, including the exact
  unsupported semantic;
- `next_action` records one compact missing step for a component. Put a step
  shared by several components in the top-level `next_actions` list instead of
  copying it into every row.

Shared product, version, surface, destination, and installer facts belong in
`target`. A successful parse or file transaction can establish delivery, but it
does not establish native discovery, behavior, or enforcement.

| Layer | Proves | Does not prove |
| --- | --- | --- |
| Inventory | The expected canonical sources are listed exactly once | Any target installation |
| Source | Canonical syntax, links, tests, and deterministic behavior covered by tests | Native discovery or events |
| Installed structure | The target copy parses and references valid paths | That the product loaded it |
| Native discovery | The current product exposes the installed identity | Correct behavior or enforcement |
| Representative behavior | A safe trigger produced the required effect | Unprobed products, interfaces, tools, or roles |
| Preservation and convergence | Owned changes preserve unrelated state and repeating adaptation adds no differences | Future product upgrades |

## Per-component evidence

This matrix defines adapter behavior evidence. Apply the reuse and execution
boundary below before deciding which checks an ordinary installation needs.

Keep a concise current evidence summary in the final report: the product version
and surface, identity, probe, observed result, and any missing proof. In state,
use `reason` only for an actual limitation and `next_action` only for the current
missing step. Shared target details and shared next actions need not be repeated
in every row. Do not persist raw output or create a separate execution log.
Remove obsolete limitations and actions when the evidence resolves them.

- **Credentials:** command identity resolves to the intended executable;
  clipboard or protected prompt registration and protected retrieval work
  without printing a value; the centralized non-secret index remains ignored.
- **Instruction:** a fresh native session outside the MAINFRAME project shows
  that the effective global layer contains the MAINFRAME semantics alongside
  preserved user content. Source text inherited from the installation task or
  project instructions does not prove global loading.
- **Skill:** native listing or routing exposes each stable name, and harmless
  loading resolves its body and required relative resources. Do not carry out
  the skill's operational task merely to prove loading.
- **Agent:** native discovery exposes each exact role; the role loads its
  required method; a harmless allowed action works; a harmless prohibited action
  is denied when enforcement is part of the role. Parsing an agent file proves
  none of these runtime properties.
- **Command:** each user-visible identity resolves to its intended body, loads
  on explicit invocation when supported, preserves the no-argument contract,
  and does not silently invoke a different agent or mode. Use the safe loading
  procedure in the [command guide](components/commands.md); installation does
  not authorize execution of the command's actual workflow.
- **Hook:** a real native event reaches the installed wrapper with the expected
  input; a clean case is silent; a safe finding has the required advisory or
  blocking effect; operational failure follows the canonical fail behavior.
  Test the lifecycle and recipient boundaries in the
  [hook guide](components/hooks.md#verify).
- **Integration or permission:** native effective configuration exposes the
  stable registration; a harmless capability probe works; unrelated entries and
  secret boundaries remain unchanged.

A shared probe may establish common packaging or transport only when the
identical mechanism is demonstrated. It does not substitute for discovery of
each identity or different behavior and permission boundaries.

## Routine installation and adapter validation

For any maintained product mapping, ordinary installation is the finite
`plan`, `apply`, and `verify` sequence from its product procedure. Those actions
run deterministic inventory, rendering, destination, ownership, preservation,
and convergence checks. A successfully delivered component may therefore have
`delivery: installed` and `verification: pending`.

Do not append native discovery, model or agent sessions, browser interaction,
credential operations, hook lifecycle probes, repository test suites, or an
acceptance campaign to an ordinary installation. Reuse applicable adapter
behavior evidence only when source, mapping, runtime, permissions, and mechanism
are unchanged.

An installation pass can finish with delivered components awaiting verification.
Give one exact activation, reload, or fresh-session handoff when the product
requires it, record it once in `next_action` or top-level `next_actions`, and
return. Do not wait, poll, operate another interface, or repeat discovery while
the user completes it. Preserve a deliberately disabled component. Never manufacture
behavior evidence from a successful install or describe `delivery: installed`
as full native acceptance while `verification` remains `pending`.

When a later accepted native check completes a recorded handoff, remove that
action while marking only the proven rows as passed. An unchanged reconciliation
must preserve the resolved absence; a delivery, mapping, version, or surface
change may add the handoff again.

Behavior probes belong to adapter development, an explicitly requested acceptance
run, or bounded diagnosis of a concrete observed failure. Revalidate the affected
contract after relevant source, runtime, permission, or mapping changes. An
unknown runtime requires a compatibility decision, not an automatic full audit.
Use the matrix above and the smallest proof plan below for that separate work.

## Plan the smallest complete proof

Before starting model-driven probes, separate deterministic checks, shared
native mechanisms, and distinct behavior boundaries. Validate every identity
and installed resource directly. Reuse an available native session for harmless
loading checks when its catalog, selected identity, body reads, and required
resource reads are observable. A new model session per file is unnecessary;
fresh sessions remain necessary for launch-time loading and isolation checks.
Keep the per-entry installation and state loop; reuse evidence only while its
source, configuration, permissions, runtime, and tested mechanism are unchanged.

Apply the [model selection policy](../../instructions/global.md#agents) to
installation probes even before global instructions are installed. Use a
sufficient supported model and reasoning effort, honor the user's selections,
and verify effective settings when available. When evaluating a specified
installer model, do not silently use a stronger model for its probes or helpers.
Record shared probe settings once; model price or reputation is not evidence
that an installation is correct.

Define the expected observable effect before each probe. A zero process exit,
nonempty final reply, or model claim that it loaded a component is insufficient.
An explicit path in the probe can prove file loading but cannot by itself prove
native selection. Check the selected identity and actual successful reads. For
hooks, first establish that the exact fixture callback ran; silence from an
unregistered fixture cannot prove clean behavior or safe disable. For roles,
inspect the actual child and native action result.

Read relevant documentation and schemas once per mechanism and retain their
small useful conclusions. Inspect diagnostic fields needed for the current
claim instead of printing entire schemas or repeated component bodies. Rerun a
probe only when a change or unresolved boundary gives it a new question to answer.

## Desktop and CLI

The default target is the surface running the installation request. A Desktop
installation does not start the product's CLI, an interactive terminal client, a
separate app-server, or CLI model probes. A CLI installation does not open or
automate Desktop. Running the shared Python installer through a shell is still
allowed; it does not start either agent product interface.

Add the other surface only for an explicit user request. Shared on-disk
configuration may affect both consumers; preserve that owner without duplicating
files or claiming to have tested both. An unrequested surface is outside scope,
not a missing acceptance check. If current-surface discovery, activation, or
reload is unavailable, report that exact handoff or gap instead of using the
other interface as a substitute.

When both surfaces are explicitly requested, do not infer one from another.
Prove them separately when they have
different processes, configuration roots, reload behavior, sandboxes, event
dispatch, or bundled versions. When they demonstrably share one effective
configuration and runtime mechanism, record that evidence once and test the
remaining distinct boundaries. Two executable paths to the same engine do not
automatically require duplicate model-driven body reads, and neither path alone
proves a running Desktop session reloaded. A failure in an older CLI does not
establish a limitation in a newer Desktop runtime, or conversely.

For a UI-only surface, use visible native discovery and a harmless user-like
interaction. For a CLI surface, use its listing, diagnostic, or execution path.
A live Desktop task's native skill catalog and successful body/resource reads
can prove discovery and loading in that task. Do not leave those checks pending
solely because a menu was not inspected; user-facing selection and other UI
behavior still require their own proof when part of the contract.
A successful CLI parse does not prove Desktop reloaded a hook. If the requested
surface cannot be tested now, keep its verification `pending`.

One aggregate row must not conceal different results. The final report names
each requested surface and any gap. Delivery is `installed` when the target
artifacts for the row were delivered on every requested surface, even if native
verification remains `pending`. Delivery is `pending` while required delivery
work is incomplete. Use `unsupported` only when an established product
limitation prevents the canonical component; omit `verification` for that row
and report any retained partial representation explicitly.

## Negative checks

Full native acceptance requires every non-unsupported row to have
`verification: passed` and also confirms:

- every state entry has an accurate delivery outcome, every supported delivered
  row has passed verification, and every unsupported row has a precise reason;
- all target placeholders and adapter-only source directives are resolved or
  removed in installed copies;
- no broken MAINFRAME-owned symlink, duplicate identity, or duplicate
  registration remains;
- a second bounded reconciliation with the same input produces equivalent
  installed content and effective registrations;
- no repository documentation, tests, local state, archive, or development
  configuration was installed globally;
- no secret value appears in ordinary configuration, state, diagnostics, logs,
  patches, or the final report;
- authentication, histories, sessions, memories, projects, user instructions,
  unrelated components, and application-owned caches remain present;
- no MAINFRAME telemetry collector or permanent activity log was added;
- canonical sources and required resources match the pre-install baseline,
  including untracked source files and unrelated pre-existing edits;
- operation-owned temporary files, trust or permission entries, processes, hook
  state, and bytecode have been cleaned through the bounded recovery route.

## Safe hook probes

Never test a destructive guard against a real protected path or repository.
Call canonical detectors directly with synthetic payloads, then exercise the
native bridge with an isolated harmless fake action whose expected block cannot
damage state. Use temporary repositories and files for Git and edit-event
checks. An intended denial must remain harmless even if enforcement fails.
Avoid bytecode in the source checkout by using `PYTHONDONTWRITEBYTECODE=1` for
Python probes. Follow
[rollback-and-recovery.md](problems/rollback-and-recovery.md) for probe cleanup.

## Unsupported is evidence, not failure concealment

Use `delivery: unsupported` only for an established limitation of the target
product and surface: explicit current authoritative documentation or a reproducible
harmless native probe must demonstrate that a required semantic cannot be
represented. Check that evidence applies to the actual installed version. An
absent listing, failed configuration attempt, unavailable tool, timeout,
untested interface, or deprecated mechanism alone does not establish inability.
If current documentation explicitly excludes the required capability, do not
invent an impossible or unsafe probe merely to repeat that fact.

Name the missing event, enforcement, visibility, attribution, continuation, or
other exact capability in `reason`. A partial advisory does not prove a guard,
and a prompt does not prove a native permission. A fallback is supportable only
when it preserves the complete canonical contract; required semantics that are
absent make delivery `unsupported`, even when useful partial behavior is retained
and reported. An unsupported row has no `verification` field.

Use `delivery: pending` when delivery is unfinished. Use `verification: pending`
when native proof is unfinished, including after successful delivery. Record the
specific missing step in `next_action`, not `reason`. Recheck unsupported
outcomes after relevant source, adapter, configuration, or product changes.
