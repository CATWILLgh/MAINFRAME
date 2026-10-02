# Install MAINFRAME into Codex

Use this maintained route when the user sends the bootstrap from the open
MAINFRAME repository. It replaces manual per-file adaptation for Codex. Keep
the user-facing file-only invocation unchanged.

## Establish the target and plan

On macOS or Linux, use Python 3.11 or newer and Git. Select the surface running
this request under the [surface rule](verification.md#desktop-and-cli).
The native mapping was inspected against engine **0.153.4** and revalidated for
**Desktop 0.159.2** on 2026-10-02. Delivery compatibility is established from
tagged source/schema comparison and disposable-home installer checks; live
Desktop lifecycle and role acceptance remain separate. See the
[0.159.2 evidence](native/codex.md#desktop-01592-delivery-revalidation).
Do not upgrade Codex,
switch the user's model, or claim another version is verified. `plan` works
read-only; a full installation requires the tested runtime. To support a different version,
revalidate the affected native contract and update the maintained module with
its evidence, rather than bypassing the version check or writing a second installer.

CLI remains limited to the inspected **0.153.4** mapping. Desktop 0.159.2
supports the full maintained delivery route, including new complete skill
packages and the checkpoint hook. It does not require launching a CLI agent,
app-server, model probe or trust UI automation.

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

Run from this repository root. For Desktop, the installer reads only the current
task's engine version from local runtime metadata, using `CODEX_THREAD_ID`. It
does not read conversations, enumerate other tasks, or invoke an executable.
If this metadata is unavailable, use `--runtime-version` only with an engine
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
and explicit-only commands there, prepares the two
supported hook bindings, merges the narrow feedback permission, and writes the
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
the bridge. Fallow has no retained Codex binding because the available events
cannot provide an exact attributed diff without persisting source content,
mixing unrelated dirty-worktree changes, or forcing a model continuation.

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
