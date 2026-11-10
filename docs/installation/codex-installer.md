# Install MAINFRAME into Codex

Use this maintained route when the user sends the bootstrap from the open
MAINFRAME repository. It replaces manual per-file adaptation for Codex. Keep
the user-facing file-only invocation unchanged.

## Establish the target and plan

On macOS or Linux, use Python 3.11 or newer and Git. Select the surface running
this request under the [surface rule](verification.md#desktop-and-cli).
The native mapping was inspected against engine **0.153.4**, revalidated for
**Desktop 0.159.2**, and refreshed for **Desktop 0.165.0-alpha.1.2** on
2026-11-01. Delivery compatibility is established from
tagged source/schema comparison and disposable-home installer checks; live
Desktop lifecycle and role acceptance remain separate. See the
[current full-mapping evidence](native/codex.md#desktop-01650-alpha12-full-delivery).
Do not upgrade Codex,
switch the user's model, or claim another version is verified. `plan` works
read-only; a full installation requires the tested runtime. To support a different version,
revalidate the affected native contract and update the maintained module with
its evidence, rather than bypassing the version check or writing a second installer.

CLI remains limited to the inspected **0.153.4** mapping. Desktop admits
**0.153.4**, **0.159.0-alpha.12.1**, **0.159.2**, and **0.165.0-alpha.1.2**
for full delivery of the supported MAINFRAME components, including complete
skill packages, roles, explicit commands and native hooks. The mapping
accounts for every entry in the [canonical inventory](../../ADAPTATION.example.json).
The four DSH packages use [DSH's own delivery route](dsh-adapter.md).
Skills and command projections
are delivered only to `$CODEX_HOME/skills`; role files use `$CODEX_HOME/agents`.
The shared `.agents/skills` root is never a delivery destination; an older
receipt can authorize retirement of its unchanged owned files during migration.
It does not require launching a CLI agent,
app-server, model probe or trust UI automation.

The current full route retains the existing subagent-selection registration for
the verified collaboration interface and installs the Fallow detector plus a
non-blocking `PostToolUse` advisory for supported exact patches. Fallow uses
only bounded in-memory reconstruction of the addressed files; it never scans a
dirty worktree for attribution or stores source/diff text. Runtime readiness
includes `ruff`, `oxlint`, `semgrep` and `fallow`. The native callback gives
Fallow seven seconds within its ten-second handler timeout.

Quality completion checks now bind both primary `Stop` and worker
`SubagentStop`, with worker state isolated by native session and agent identity.
One positive revalidation requests a repair continuation. A still-positive retry
terminates with a visible unresolved reason and retains state for the next user
turn. This is bounded recovery, not proof that Codex marks the turn as failed.
Full quality parity remains unsupported, alongside full Fallow completion timing
and the two shell guards' actual-tool-workdir-dependent guarantees. The plan
reports all four retained partial bindings explicitly.

New hook definitions require native review/trust after delivery. The installer
preserves existing trust state, hook order, deliberate disables, foreign files,
user roles and configuration; it never writes native trust hashes. Discovery,
recipient delivery and native execution remain pending until observed on this
surface. Other nearby versions and current-version CLI are not admitted.

Desktop **0.154.0-alpha.6.2** also supports a bounded update of an existing
same-source installation. The installer recognizes the exact prerelease string
from current-task metadata. It accepts only replacement of existing Markdown
instructions/resources and role descriptions/bodies, with skill discovery metadata,
role permissions, file modes, executable resources, hook commands, and global
configuration unchanged. The sole registration migration removes
`additionalContextLimit` from the installer-owned `Stop` handler: Codex ignores
that field for events which cannot emit additional context and reports a configuration
warning. New or removed files, source moves, fresh
installation, CLI use, and native packaging changes still require a validated
mapping. Use the same `plan`, `apply`, and `verify` commands below; reports identify
this bounded-update mode. Known 0.153.4 hook limitations become pending compatibility
checks, not claimed unsupported facts about the newer runtime. See the
[bounded evidence](native/codex.md#prerelease-content-updates).

Desktop **0.162.0-alpha.17.2** supports a narrower repair of an existing
same-source installation: replacement of the receipted, installer-owned
`mainframe-destructive-operations` detector, with its mode, hook definitions,
transport, dependencies, other payload and global configuration unchanged.
This does not admit a fresh install, text update or general runtime mapping.
Use the interpreter already named in the installed hook commands when it remains
available; changing the installer interpreter would change native definitions
and is rejected by this repair boundary. The maintained `plan`, `apply` and
`verify` commands remain the route; never copy a detector manually.

The detector needs only Python's standard library. This bounded repair leaves
unrelated analyzer dependencies untouched and still reports their readiness.
`verify` adds `scoped_update_matches`: true proves this narrow reconciliation
converged. The existing full `structure_matches` result and exit status still
require all installed hook dependencies, so they can remain false/nonzero when
an unrelated dependency is missing. Report that distinction, preserve native
trust and disables, and separately confirm the repaired active pre-shell
behavior. See the [detector-update evidence](native/codex.md#desktop-01620-alpha172-detector-repair).

Desktop **0.163.0-alpha.11** supports the bounded subagent-selection update of
an existing same-source installation. It installs the explicit model/effort
guard, updates the owned transport, and appends its PreToolUse registration;
unrelated payload and native definitions must remain unchanged. This is not a
full runtime mapping or fresh-install route. `verify` reports
`scoped_update_matches` independently of unrelated analyzer readiness. See
[the native acceptance and naming evidence](native/codex.md#explicit-subagent-selection).
Trust the final new hook in Desktop after delivery; the installer does not
write trust hashes. Its disable/remove lifecycle uses the ordinary maintained
commands and preserves late-callback silence.

Desktop **0.164.0-alpha.11.1** supports an existing same-source installation's
Markdown update only. The global instruction owner, existing skill/command
Markdown, discovery metadata except descriptions, file modes, executable payload,
hook registrations, role definitions and global configuration retain their
existing boundaries. No files may be created or removed. The previously installed
subagent-selection binding is preserved; its behavior on this runtime is not
newly certified. The update does not provision unrelated analyzers and reports
their readiness separately from `scoped_update_matches`. This is not a fresh
installation or full native mapping. See the [text-update comparison](native/codex.md#desktop-01640-alpha111-text-update).

### Deliver one skill on Desktop

Desktop **0.165.0-alpha.1.2**, **0.166.0-alpha.5.1**, and **0.167.0-alpha.3.2**
support the explicit skill-only route for an existing same-source installation
with a matching ownership receipt and schema-2 adaptation state. The tagged
reader supports complete packages under `$CODEX_HOME/skills`. The two later
versions have been revalidated for this route alone.
See the source evidence for [0.165.0](native/codex.md#desktop-01650-alpha12-skill-only-delivery),
[0.166.0](native/codex.md#desktop-01660-alpha51-skill-only-delivery), and
[0.167.0](native/codex.md#desktop-01670-alpha32-skill-only-delivery).

```sh
python3 -B install.py codex plan --surface desktop --skill mainframe-sentry
python3 -B install.py codex apply --surface desktop --skill mainframe-sentry
python3 -B install.py codex verify --surface desktop --skill mainframe-sentry
```

Use one exact identity from the inventory's `skills` category. Commands packaged
as skills are excluded. Keep the same target and observed runtime options for
all three commands. `--runtime-version` follows the evidence rule below.
The route uses the ordinary approved resource selector, ownership checks, lock,
transaction and recovery journal. Intended new source resources must be staged
before planning; it does not stage them or alter existing partial staging.

Only the selected skill package and its receipt records and adaptation row are
reconciled. Existing hooks, registrations, global instructions, configuration,
permissions, native trust, deliberate disables, unrelated files and unrelated
state rows are preserved. A previous shared-root destination requires its own
authorized migration. Owned edits and conflicting foreign files stop delivery.

Skill-only verification checks `scoped_update_matches` for file convergence.
It neither checks nor provisions unrelated hook analyzers and makes no full
`structure_matches` claim. For `mainframe-openspec`, apply prepares the
[shared CLI](components/integrations.md#shared-openspec-cli) and verify also
requires `runtime_support.ready`. The adaptation state's top-level target and
existing receipt fingerprint retain their previous full-installation meaning.
The report identifies the current skill-delivery runtime. The selected row remains
`verification: pending` with a fresh-task discovery handoff until discovery is
observed. Other runtimes, CLI, fresh installs and source moves are rejected by
this route. Do not use whole-product apply to deliver a single skill on this
runtime.

### Deliver the backlog command and guard on Desktop 0.165.0-alpha.1.2

An existing same-source installation with a matching receipt and schema-2 state
can receive the canonical `todo` command and `mainframe-todo-limits` detector
through the bounded route:

```sh
python3 -B install.py codex plan --surface desktop --todo
python3 -B install.py codex apply --surface desktop --todo
python3 -B install.py codex verify --surface desktop --todo
```

This installs the explicit-only `todo` skill, updates the owned hook bridge,
and appends one `PreToolUse` group matching `apply_patch`. It preserves other
registrations and their order, receipt metadata, adaptation rows, configuration,
native trust and disabled markers. It uses the ordinary lock, ownership checks
and recoverable transaction; it neither provisions nor checks unrelated analyzers.
Verification reports `scoped_update_matches`, with native behavior pending.
Other runtime versions, CLI, fresh installations and source moves are rejected.

The [official slash-command guide](https://learn.chatgpt.com/docs/reference/slash-commands)
places enabled skills in the Desktop slash menu. Type `/`, filter for `todo`
and select it; literal `/todo <prose>` execution on this exact Desktop build
has not been observed. The documented explicit alternative is `$todo <prose>`.
The package accepts caller prose and disables implicit invocation, as described
in the [skill guide](https://learn.chatgpt.com/docs/build-skills).

Review and trust the new hook definition in Desktop after delivery, then confirm
the addressed oversized edit is denied. The installer never writes trust hashes.
The guard examines only attributed `apply_patch` edits to `.docs/todo` and
`.docs/todos/*.md`; shell writes and other tools are outside this binding.
Without a usable native `cwd`, this binding remains neutral, including absolute
patch paths. Write a new detail note before
adding its index link, so its target exists when checked. See the
[native evidence](native/codex.md#desktop-01650-alpha12-backlog-command-and-guard).

Run from this repository root. For Desktop, the installer reads only the current
task's engine version from local runtime metadata, using `CODEX_THREAD_ID`. It
does not read conversations, enumerate other tasks, or invoke an executable.
Thread creation metadata can be stale after an app upgrade. Use `--runtime-version`
to override it only with an engine
version established by current app evidence. Never substitute the app release
number, the CLI on PATH, or this document's tested version. An unavailable
version is a precise handoff, not permission to search session histories.

For Desktop:

```sh
python3 -B install.py codex plan --surface desktop
```

For an installation running in CLI:

```sh
python3 -B install.py codex plan --surface cli
```

Only CLI uses the Codex executable for version discovery; use `--executable`
when that CLI has an explicitly resolved path. Desktop rejects `--executable`
and `--native` and never launches the CLI or a separate app-server.
`--codex-home` selects an explicitly
resolved native configuration home. `--home` is primarily for isolated fixture
tests; a fixture is not native installation evidence. No command searches other
MAINFRAME checkouts, imports session histories, or reads credential stores.

The plan groups file changes by component. Add `--details` only when individual
paths help inspect a conflict. Read the exact reported global instruction owner
and [canonical global instruction](../../instructions/global.md) if semantic
review is requested. Resolve actual conflicts under the
[instruction guide](components/instructions.md); compatible overlap needs no
new user approval. The review flag records the invoking agent's check, not a
requirement to ask the user to approve every installation.

## Apply once, then check convergence

Repeat the plan command with action `apply` and `--instructions-reviewed`, then
with action `verify`. Keep the same surface, runtime, and configuration options.

The installer validates the inventory and ignore rules, copies complete skill
resources into the private `$CODEX_HOME/skills` directory, packages exact roles
and explicit-only commands, prepares the supported native hook registrations,
merges the narrow feedback permission, and writes the
global instruction after its dependencies. An existing compatible `mainframe-secret`
helper and the non-secret index are preserved. The helper creates protected
storage through its normal operation; installation never inspects its values.

When intentionally moving to another MAINFRAME source checkout, the ownership
receipt identifies the previous source. The installer carries its non-secret
credential index to the new source when absent, rebinds the feedback root, and
preserves the old index. Different existing indexes require reconciliation;
neither is overwritten or silently discarded.

Owned files changed by the user cause a conflict before another file is written.
Identical pre-existing files may be reused without acquiring deletion rights.
Unusual commented or quoted TOML permission syntax is preserved and returned as
one precise handoff; reconcile that entry before accepting the feedback skill.
The feedback directory is created only for a real observation.

`apply` records successfully delivered components as `delivery: installed` in
`ADAPTATION.codex.json`; their native behavior can remain
`verification: pending`. `verify` deterministically checks that another
reconciliation would change nothing. Exit 0 proves delivery and convergence,
not native discovery or behavior. The four known full-hook limitations are
`delivery: unsupported` on the tested runtime, carry a precise `reason`, and
omit `verification`. The `mainframe-code-quality` row remains unsupported as a complete
contract, but its useful core is retained: pre-patch capture, post-patch advice,
and revalidating completion blocking are installed. Native `stop_hook_active`
bounds an unresolved finding to one automatic continuation per turn while
retaining it for the next user turn. Only completion-time
advisory delivery is absent.

The report also names two safe pre-shell partials. Destructive operations keep
their command-structural Git and root/home deletion guards; commit secrets keep
literal and absolute-file metadata inspection. Their workdir-dependent
guarantees remain unsupported. All four shell identities use one
`mainframe-pre-shell` registration, so a clean Bash event starts one bridge
process and emits no context. Individual disable markers still apply inside
the bridge. Desktop **0.165.0-alpha.1.2** retains the immediate Fallow advisory
described above. Earlier full mappings have no Fallow binding.

## Finish the current-surface installation pass

Use this finite checklist under
[routine installation](verification.md#routine-installation-and-adapter-validation):

1. Run `plan`, `apply`, and `verify` with the same target options. Confirm
   `verify` reports convergence and no unresolved ownership or permission
   conflict.
2. Read the resulting `ADAPTATION.codex.json`. Report delivered components,
   unsupported limitations, and the one shared activation or fresh-session
   handoff from top-level `next_actions`.
3. Return after that handoff. Leave delivered but unproved rows as
   `delivery: installed` with `verification: pending`.

An explicitly requested current-surface validation updates the passed component
rows and removes a completed top-level reload or activation action. Repeating
`verify` with unchanged files preserves that resolved state. A later delivery
change restores the shared fresh-session handoff because the affected native
loading boundary must be checked again.

The three read-only roles share one top-level permission-boundary action while
that behavior remains unproved. Do not repeat the same action in every role row.

Do not add `--native`, inspect a native catalog, launch `codex exec`, create or
poll model sessions, spawn role probes, request fixed acknowledgement phrases,
operate a browser or credential store, cycle hooks, or run the repository test
suite during this pass. Such probes belong to adapter validation or an
explicitly requested acceptance run. A missing proof is recorded once; it is not
a loop condition for more native calls.

## User activation of hooks

The installer prepares registrations; the user grants native trust when Codex
requires it. Do not automate the trust UI, write trust hashes, or switch to CLI
from Desktop to activate hooks. Preserve existing native trust and deliberate
disables; do not ask for activation again when the current surface already
confirms all three installed hook identities are trusted and enabled.

Give one short final handoff naming `mainframe-secret-access`, `mainframe-rg-short-replace`, and
`mainframe-code-quality`:

- In CLI, ask the user to open `/hooks`, review, and trust those MAINFRAME
  definitions.
- In Desktop, identify its hook trust control only from current app evidence.
  Do not assume CLI's `/hooks` exists there. If no control is exposed, say that
  registration is prepared but activation in this app is not established.

Keep affected hooks at `verification: pending` after their files and
registrations have `delivery: installed`, until activation is confirmed on the
current surface. Put the shared activation step in top-level `next_actions`,
finish independent installation work, and return. Do not poll or rerun discovery
while waiting. An explicitly requested follow-up can check the state once after
the user completes the step.

## Adapter validation is separate

For changes to the adapter, a concrete native failure, or an explicitly requested
acceptance run, use the [behavior matrix](verification.md#per-component-evidence)
and [smallest proof plan](verification.md#plan-the-smallest-complete-proof).
Validate only affected mechanisms on the requested surface. Do not repeat known
gaps, use a different surface as a substitute, or upgrade an installation result
to full acceptance from catalog checks alone.

## Disable, enable, remove, recover

```sh
python3 -B install.py codex disable
python3 -B install.py codex enable
python3 -B install.py codex uninstall
python3 -B install.py codex recover
```

Use `--hook mainframe-secret-access`, `--hook mainframe-rg-short-replace`, or
`--hook mainframe-code-quality` for an individual disable or enable. These lifecycle
commands do not require a working Codex executable.
Disable writes a marker before the detector can load and waits for the existing
five-second callback timeout to elapse. Updating preserves deliberate disables.

Uninstall first validates ownership, disables the hooks, waits for in-flight
callbacks, and removes only owned artifacts and registrations. Its cached
command retains `/bin/sh` plus an inline implementation-existence check, so even
after all owned hook files disappear it returns a neutral result. This route
does not delete a registered entrypoint: the retained entrypoint is the native
inline command and the system shell. Arbitrary older adapter commands still
require the [general retirement sequence](problems/rollback-and-recovery.md#retire-hooks-safely).

The protected `mainframe/installation.json` below the resolved Codex home stores
only current ownership, hashes, and reconciliation metadata. A temporary
`mainframe/recovery.json` holds narrow file snapshots during a write transaction
and is removed after commit or successful rollback. If interrupted, `recover`
restores only matching before/after states and refuses to overwrite a concurrent
edit. Keep that recovery file private; do not paste it into a conversation.

Uninstall preserves credential descriptions and stores, user-owned matching
files, unrelated configuration, real sessions, native trust/cache data, and
the empty installer lock used to coordinate writers. Empty owned component
directories are removed only when no unrelated file remains.

## Existing installations without an ownership receipt

Do not infer ownership from a `mainframe-*` name alone. Conflicting old copies,
old hook registrations, or the former managed instruction supplement need one
scoped migration under [existing-installation.md](problems/existing-installation.md).
The installer deliberately does not restore a profile snapshot or overwrite an
unrelated copy to get past that boundary. Clean acceptance tests use a
separately prepared baseline; an ordinary install does not reset a profile.

## Maintain one implementation

Change canonical content in its existing source. Change native packaging and
lifecycle in [installer/codex.py](../../installer/codex.py), transport in
[codex_hook.py](../../installer/codex_hook.py), and common file transactions in
[core.py](../../installer/core.py). Generated global copies are not another
source tree. The native reference and relevant tests must change with the
mapping; a successful offline fixture test does not update an acceptance badge.

## Migration from the shared skill root

The maintained adapter now uses `$CODEX_HOME/skills` for its 15 skill packages
and seven explicit-only commands. Ordinary `plan`, `apply`, and `verify` perform
the migration using the existing ownership receipt. Old shared copies are
removed only when installer-owned and unchanged; customizations stop the plan
before writes, and unrelated resources remain. Role method links follow the
new destination. After a successful transaction, the installer also removes
its old shared directories when they are empty; it preserves any directory
that contains user or foreign material. No symlink back into the shared
discovery root is created.
See the [native evidence](native/codex.md#private-user-skill-destination) for its
runtime scope. Native primary-session refresh remains a user handoff where the
current task's catalog is stale.

If ZCode has path-specific disable overrides for the former shared commands,
remove only those now-orphaned MAINFRAME entries when updating ZCode is also
authorized and their exact old skill files no longer exist. Preserve existing
ZCode-native commands and all unrelated settings.
