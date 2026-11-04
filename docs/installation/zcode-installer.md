# Install MAINFRAME into ZCode Desktop

Use this maintained route when the installation request is running in ZCode
Desktop from this MAINFRAME checkout. The original inspected mapping targets macOS
ZCode build **3.11.2.6792**. Full Desktop delivery is also supported on
**3.14.4.7912** and **3.17.1.9553** after inspection of their shipped native
contracts. The current build includes immediate Fallow advice from exact native
Write/Edit responses. New conversation acceptance remains separate. The older **3.14.3.7762** route permits bounded
skill updates and the exact validated pre-shell transport consolidation in an
existing same-source installation; other native-hook changes, roles, commands,
and permissions remain blocked. Version detection reads the selected application's plist;
it never starts the ZCode CLI, another model, or an app-server.

The agent does not develop the adapter during installation. Native mappings and
known gaps belong to [zcode.md](native/zcode.md); mechanical behavior belongs to
[installer/zcode.py](../../installer/zcode.py),
[installer/zcode_hook.py](../../installer/zcode_hook.py), and shared installer
modules. Unknown builds need a separately scoped compatibility check.

## Deliver one skill

Use this route on the inspected full-mapping builds and Desktop **3.17.2.9661**
with an existing same-source installation and matching receipt and adaptation
state. The new build was inspected for the private skill reader only. See the
[bundled reader evidence](native/zcode-evidence.md#desktop-31729661-private-skill-reader).

```sh
python3 -B install.py zcode plan --surface desktop --skill mainframe-openspec
python3 -B install.py zcode apply --surface desktop --skill mainframe-openspec
python3 -B install.py zcode verify --surface desktop --skill mainframe-openspec
```

The route reconciles the selected package under `~/.zcode/skills/` and its
receipt and adaptation records. It leaves hooks, commands, roles, configuration
and analyzers alone. `scoped_update_matches` proves selected-file convergence.
Refresh Skills in Desktop settings and open a new conversation for discovery.

## Deliver only /todo

Build **3.17.1.9553** also retains a narrow route for `/todo` in an existing,
same-source receipted Desktop installation. The bundled command expander appends text supplied after
`/todo` as user arguments; the workflow records or updates the active worktree's
`.docs/todo` index and `.docs/todos/*.md` notes. Write the note before its index
entry. See [the command](../../commands/todo.md) for the agreed groups and limits.

```sh
python3 -B install.py zcode plan --surface desktop --todo
python3 -B install.py zcode apply --surface desktop --todo
python3 -B install.py zcode verify --surface desktop --todo
```

This route delivers only `commands/todo.md`, the canonical task-limit detector,
its maintained bridge, and one user-level `PreToolUse` registration matching
`Write|Edit`, plus their receipt and adaptation rows. It provisions no analyzers
and preserves other components, user configuration, trust, native disable
toggles, disable markers and existing verification evidence. Conflicting files
or registrations stop delivery for reconciliation. Normal full delivery on
previously supported builds also includes these components.

`mainframe-todo-limits` denies only a positive addressed index-row or note
violation. Native `Write` content and `Edit` replacements are projected through
the canonical detector before execution; untouched rows remain outside the
check. Other write paths, including shell writes, have no new binding. The
registration is primary-runtime only; subagent coverage and fresh Desktop
acceptance are not established. [Current bundle evidence](native/zcode-evidence.md#desktop-31719553-task-command-and-pre-edit-guard)
supports this narrow mapping. Open a new Desktop session after delivery. A
deliberate global hook disable remains disabled and is reported explicitly.

## Plan, apply, verify

Desktop build **3.14.5.7961** permits a bounded content update of an existing
same-source installation: new or updated Markdown skill files, the existing
managed global instruction and the existing destructive-operations detector,
with ownership checks and unchanged modes. It rejects removals, new instructions
or detectors, other executables, hook transport/registrations, roles, commands
and settings.
This does not authorize fresh installation or establish full native behavior
for that build. The report names this narrow mode. See the
[skill-delivery evidence](native/zcode-evidence.md#desktop-31457961-skill-delivery).

From the repository root:

```sh
python3 -B install.py zcode plan --surface desktop
python3 -B install.py zcode apply --surface desktop
python3 -B install.py zcode verify --surface desktop
```

Read the plan first. If it requests semantic instruction review, read the exact
existing ZCode global instruction and canonical `instructions/global.md`, resolve
actual conflicts, then add `--instructions-reviewed` to apply. Do not ask for
permission to merge compatible instructions. A conflicting user change requires
its exact decision; it does not authorize broad cleanup.

`--zcode-app` selects an explicitly located macOS application. `--zcode-home`
selects the actual target configuration root. `--home` and an explicit
`--runtime-version` support isolated development fixtures; fixture results never
establish native loading. A supplied live runtime cannot override a contradictory
application build. No option launches a CLI agent.

## Existing manual GLM installation

When the plan identifies the reviewed manual ZCode installation, run:

```sh
python3 -B install.py zcode plan --surface desktop --adopt-existing
python3 -B install.py zcode apply --surface desktop --adopt-existing
python3 -B install.py zcode verify --surface desktop
```

Adoption recognizes canonical-derived skills, roles, command formats, the exact
reviewed wrapper fingerprint, and matching detector copies. It rejects changed
files or mixed hook registrations. The state file alone never grants ownership.
The optional mainframe-init memory section is removed: writing a memory file did
not establish native recall. No memory experiment is run by this installer.

The old five hook callbacks are explicitly disabled before registrations switch.
Their callable files and dependencies remain reachable for cached sessions and
in-flight calls. The new maintained wrapper is installed at a separate path.
A new session loads the new registration; it does not prove every older session
forgot its callback. Retain the old inert paths until their scopes have unloaded
them, following the [retirement procedure](problems/rollback-and-recovery.md#retire-hooks-safely).
Do not delete an old wrapper merely to make cleanup look complete.

## Delivered mapping and known gaps

The program prepares every complete skill package listed in the
[inventory](../../ADAPTATION.example.json), seven native agent roles,
seven native slash commands, the narrow `mainframe-tickets-find` skill projection
needed by noninteractive automations, shared credential helper/index integration,
and the global instruction. It preserves unrelated target files and configuration.
Commands retain explicit invocation, and shared command-skill collisions are
handled only through exact ZCode path overrides. A Codex installation using its
private skill root needs no such override.

Role model, thought-level, color, and AGENTS.md-injection choices saved through
ZCode Settings are preserved as compatible native metadata and are not copied
into defaults for other installations. Body, routing, and tool-boundary changes
still stop reconciliation. ZCode's removal of a final command-file newline is
accepted only when the remaining bytes exactly match the maintained rendering.

The maintained transport registers four primary-runtime pre-shell hooks:
`mainframe-secret-access`, `mainframe-rg-short-replace`, `mainframe-destructive-operations`, and `mainframe-commit-secrets`.
They share one product-private pre-shell process registration; this changes
only transport cost, while the four canonical components, decisions, and
individual disable controls remain separate.
The destructive guard captures the native workspace root on `SessionStart`
(`startup`, `clear`, `compact`, or compatibility `resume`), then combines it with the actual mutable Bash cwd from
`PreToolUse`. Missing root capture never guesses from a dirty worktree or
transcript. Commit inspection uses the actual pre-command cwd.

Positive findings deny only the relevant tool call; advice never grants or
changes native permissions. The inline system-shell entrypoint stays neutral if
its implementation is disabled or absent. Output is bounded in serialized bytes,
never truncated JSON.

It also registers `mainframe-code-quality` around native `Write|Edit`: capture before,
successful or failed post attribution, and a `Stop` callback that blocks only
while an introduced finding still exists. Advisory-only Stop output remains
silent because ZCode otherwise delivers it by forcing another model turn.

The installer report supplies current delivery counts from the exact inventory.
Two completion contracts remain unsupported:
`mainframe-code-quality` and `mainframe-fallow-quality` require non-blocking completion advice.
ZCode collects `Stop` advice but delivers it to the model only with a new model
continuation. The useful mainframe-code-quality core is installed and reported as a
retained partial binding, but it is not the full canonical contract. Do not
silently change timing or force advice through a completion block.

On **3.17.1.9553**, `mainframe-fallow-quality` also has a retained partial
binding: an immediate `PostToolUse` advisory for attributed TS/JS `Write|Edit`
results. Native responses supply the original content and actual replacement;
the bridge compares the addressed postimage and builds its diff in memory.
Missing, conflicting, oversized or concurrently changed attribution produces
bounded unavailable advice. No source or diff is retained. The current full
route verifies the tested Fallow dependency alongside Ruff, Oxlint and Semgrep;
the `/todo`-only route provisions none of them.

The current native `Agent` input exposes neither a per-call model nor reasoning
effort. `mainframe-subagent-selection` is therefore reported as unsupported with
no runtime denial. User role `model`/`thoughtLevel` presets are preserved as
native configuration. A still-positive quality Stop retry carries an explicit
unresolved reason; ZCode caps repair continuations at three. Its parser has no
non-blocking final warning channel equivalent to Codex's, so a final green
quality result is never inferred from reaching that cap.

The inspected default subagent runtime does **not inherit hook runners**.
The maintained registrations protect the primary runtime; they do not establish
protection of delegated tool calls. These limitations are supported by the
[bundled-runtime evidence and reproducible probe](native/zcode-evidence.md).
They are not research assignments for the installing agent.

## Stop after delivery checks

`verify` proves files, resources, configuration reconciliation, and convergence.
It does not call skills or commands, spawn roles, use credentials, launch a
browser, or test native hook dispatch. Delivery and native verification have
separate schema-2 fields in `ADAPTATION.zcode.json`.

After successful verification, report the unsupported full contracts, retained
partial bindings and primary-only hook coverage. When skill
files changed, ask the user to use **Settings -> Skills -> Refresh** once and
then open a new ZCode Desktop session; retain that handoff in adaptation state
until native acceptance clears it. Otherwise ask only for a new session. Preserve a deliberate
global hook disable and report it rather than silently enabling it. User trust
or activation, if requested by the app, is a user handoff. Do not automate or
poll the UI. Use the [bounded Desktop acceptance procedure](native/zcode-acceptance.md) when
that work is explicitly requested. Native acceptance is separate requested work; do not prolong an
installation to turn every verification field green. The installer report already
contains delivery counts, limitations, and handoff; do not repeatedly write ad-hoc
JSON parsers to rediscover those same results.

## Disable, enable, remove, recover

```sh
python3 -B install.py zcode disable
python3 -B install.py zcode enable
python3 -B install.py zcode uninstall
python3 -B install.py zcode recover
```

Use `--hook NAME` with an identity from the inventory's `hooks` group for an individual hook.
Disable markers are checked by the cached inline launcher; they do not depend
on a native configuration reload. Uninstall disables first and waits for the
bounded maintained callbacks before retiring implementation. It preserves
foreign files, reused instructions/helpers, credential metadata, unrelated
configuration, and any necessary inert manual callbacks. `recover` restores an
interrupted file transaction only when concurrent user changes do not conflict.
No lifecycle command runs a native acceptance campaign.


## Skill reminders

The installer delivers the shared positive-only reminder method and this
product's [native binding](../../hooks/skill-reminder-routing.md#native-bindings).
An already considered skill stays quiet; reminders neither block nor continue
a model. Existing disable choices are preserved. Start a fresh Desktop
conversation after updating registrations; file convergence does not establish
native receipt or skill application.

Native role settings (`color`, `model`, `thoughtLevel`, `injectAgentsMd`) remain
per-installation choices. Receipts separately hash the managed role core, so a
later canonical-body update can preserve independently changed settings while
still rejecting arbitrary local edits to role bodies or tool boundaries. Older
receipts without a core hash can need one explicit semantic reconciliation.

## Source relocation

On a supported full-update build, updating from another source checkout retains
the existing non-secret credential index at its established path. The ownership
receipt records code source and credential source separately. Relocation never
merges, overwrites, or deletes credential descriptions. A missing or symlinked
retained index stops the update for explicit reconciliation. Older bounded-update
builds still require the same source root.
