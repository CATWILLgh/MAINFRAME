# Install MAINFRAME into ZCode Desktop

Use this maintained route when the installation request is running in ZCode
Desktop from this MAINFRAME checkout. The original inspected mapping targets macOS
ZCode build **3.11.2.6792**. The **3.14.4.7912** mapping was revalidated against its shipped hook parser,
context consumers and current official documentation. New conversation acceptance
remains separate. The older **3.14.3.7762** route permits bounded
skill updates and the exact validated pre-shell transport consolidation in an
existing same-source installation; other native-hook changes, roles, commands,
and permissions remain blocked. Version detection reads the selected application's plist;
it never starts the ZCode CLI, another model, or an app-server.

The agent does not develop the adapter during installation. Native mappings and
known gaps belong to [zcode.md](native/zcode.md); mechanical behavior belongs to
[installer/zcode.py](../../installer/zcode.py),
[installer/zcode_hook.py](../../installer/zcode_hook.py), and shared installer
modules. Unknown builds need a separately scoped compatibility check.

## Plan, apply, verify

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
Two hook contracts remain unsupported in the inspected builds:
`mainframe-code-quality` and `mainframe-fallow-quality` require non-blocking completion advice.
ZCode collects `Stop` advice but delivers it to the model only with a new model
continuation. The useful mainframe-code-quality core is installed and reported as a
retained partial binding, but it is not the full canonical contract. Do not
silently change timing or force advice through a completion block.

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

After successful verification, report the two unsupported hooks and primary-only hook coverage. When skill
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
