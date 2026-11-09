# DSH plugin packages

The [MAINFRAME inventory](../../ADAPTATION.example.json) lists four native
plugin packages that target DSH `0.2.2-rc.1`.

- [Activity Analytics](../../plugins/dsh/activity-analytics/README.md) reports
  profile-local activity and summed agent time. It requires a Host with `node:sqlite`.
- [Message Time](../../plugins/dsh/message-time/README.md) adds clocks for human
  input and full agent turns. Its runtime manifest declares the native Schemastery dependency.
- [Secrets Vault](../../plugins/dsh/secrets-vault/README.md) stores encrypted
  credentials using the Host Node.js runtime and built-in `node:crypto`.
- [Session Collaboration](../../plugins/dsh/session-collaboration/README.md)
  coordinates ordinary sessions across projects. It uses native session services
  and `storageDomain` with exact runtime peers for LLM, session title, storage,
  and Zod.

DSH manages these packages separately from the global MAINFRAME skills. Other
product adapters mark the four plugin entries unsupported.

## Session Collaboration

Version 0.5.1 exposes one `collaboration` tool with a required `action`:
`list_projects`, `list_sessions`, `read`, `send`, `wait`, `list_tasks`, `get_task`,
`cancel_task`, `models`, `create`, `archive`, `unarchive`, `get_model`, and
`set_model`. Action-specific input validation rejects irrelevant fields before
execution; the eight legacy tool names are no longer registered. Discovery is
progressive and read-only. Send accepts optional group/label metadata; one wait
observes 1–8 `targets` in `any` or `all` mode. Task actions expose bounded metadata.

Use an existing `workspaceId` for creation and an exact ordinary `sessionId` for
archive/unarchive. Creation accepts an optional meaningful `title`, persisted
and pinned as session metadata through the native title service. It returns the
accepted normalized title. Partial naming or model-selection failures retain the
fresh session ID. Creation leaves the new session idle. Archive uses native
`workspaceRegistry.archiveSession(id)` without `stopActivity`, after passive
queue/input checks. Native busy refusal is preserved. This is an inactivity
snapshot, **not an atomic admission lock**: activity can start between checking
and persistence, as with native archive. A racing input may be consumed by the
native loop before the archive gate rejects it, without transcript commitment.
Avoid archiving a session another actor is about to prompt. The plugin sends no
stop/clear request; no deletion, subagent creation or self-archive is exposed.
Unarchive does not wake the target.

The `models` action progressively lists providers, a provider's models, and a
model's reasoning efforts. `get_model` and `set_model` operate on one session; creation also
accepts optional `provider` + `model` with `reasoning_effort`. Selection uses
session-local `agent.model.select`, never changes global defaults, and affects
the next unprepared step rather than interrupting active work. Omit effort for
Auto; switching models never inherits the previous effort. `get_model` reports
unknown for a cold session without waking it; `set_model` may resume a cold Agent
but starts no model turn. Selection does not establish compatibility with prior
image history. Creation and selection are not atomic: preserve any returned fresh
session ID on uncertain configuration and never automatically recreate it.

Native `storageDomain` stores metadata only, with a 24-hour absolute TTL and
limits of 256 records globally / 64 per sender; pending watches are limited to
32 globally / 8 per sender. No profile paths or separate database setup are needed.

Automatic notification recovery claims an attempt before enqueueing: an ambiguous
crash requires manual task-status inspection rather than automatic replay. Deferred
notices wait for the sender's next natural model step, not merely opening its
session. They do not cold-wake the sender or rearm goals. Maintenance observes
targets read-only and never resends tasks. The
[plugin documentation](../../plugins/dsh/session-collaboration/README.md) owns the
full storage, recovery, and notification contract; metadata persistence is not a
guarantee of target execution, completion, or notice delivery.

When upgrading from an already-active 0.2.1 or 0.3.0, restart the DSH Host after
installing 0.3.1 or later; disable/enable alone does not clear leaked resources. The older
ordinary dispose listener was not invoked on native unload, leaving the storage
domain and other resources open. Version 0.3.1 uses an owned effect disposer.
Do not force-close the domain to bypass the restart.

## User installation and updates

Install **packed `.tgz` packages** for a DSH-managed copy independent of the
checkout. Directory links and Local Deployment bundles are legacy or
development routes.

1. Build from the checkout as shown below or obtain matching release archives.
   Keep the versioned archives in persistent user storage **outside the
   checkout**. A fresh Vault uses the Host's built-in `node:crypto`.
2. Use `plugin_manager` listing actions to identify installed package/entry ids.
   Use live Inspect contracts when configuring or extending plugins. Never edit
   the profile manifest/patch or run a package manager in the profile directory.
3. For a fresh installation use `install_bundle` with each absolute `.tgz` path.
   For replacement, disable/remove the previous bundle through native management,
   then install the new archive. Retain previous archives until verification so
   rollback can use the same native route. Native removal does not delete plugin
   data. Do not run old and new generations together.
4. Follow the returned `application`, `nextStep`, and warnings. A required restart
   must happen before claiming that new code is running. Observe active rows,
   Client registrations, and the actual capability separately; source tests and
   installed files alone are not native acceptance.

The package's runtime and code live in DSH-managed package storage. Analytics and
Vault choose `profileDirectory`, then Host `DSH_PROFILE_DIR` if available, then
their native installation root. The last route walks `node_modules` ancestors
and accepts only exact package aliases resolving back to this installed module;
the outermost matching root identifies the profile even through pnpm's virtual
store. DSH exposes profile variables to shell tools but Desktop may not expose
them to Host plugins. No cwd/home guess or machine-specific path is compiled in.
Data stays beneath that profile's `activity-analytics/` and `secrets-vault/`
directories. `profileDirectory` remains an advanced compatibility override.
Obsolete Vault `python` configuration is rejected, not silently ignored. Source/unrecognized layouts without explicit context fail closed.
This inference targets native profile installs, not arbitrary global npm layouts.

The repository can be deleted after packed installation. Retain the archives:
DSH saves their install specs and may need them to rebuild dependencies or roll
back. Updates are new packages installed through DSH, not live checkout changes.
This route does **not** publish to npm or provide automatic background updates.
Another user can build from an updated checkout or receive matching release
archives. An npm/HTTPS release channel would be separate publication work.

### Migrating linked/Local Deployment installations

Before replacing an older setup, list its native bundles and inspect effective
configuration. Disable the configuration-only `@mainframe/local-deployment`
first; remove it and replace the linked source packages using native management.
Do not enable the source bundle and deployment bundle simultaneously: their row
ids overlap. Remove obsolete `@local/*` packages only after identifying them.
After switching a running Desktop Host from source links to archives, fully quit
and reopen DSH before acceptance (a browser refresh is insufficient). The live
loader can retain the previous linked module even while native package inventory
and disk files show the new version; repeated installation is not a cache repair.
Also check for older background Hosts sharing the same profile. Vault deliberately
holds an exclusive lifetime writer lock; an obsolete Host can keep the new store unavailable
even after the visible Desktop restarts. Identify the lock-owning process and its
parent without reading the database; obtain permission before stopping that older
Host. Never bypass a live lock or remove the legacy advisory lock file. V2's
2.0.2+ publishes a populated `.node-owner` gate and retains `.node-lock` for old
writers. It automatically reclaims valid crashed-owner metadata only when the PID
is confirmed absent; live/reused PIDs, malformed metadata and denied probes stay
blocked. It never removes an unverifiable owner to make startup succeed. Manual
maintenance still requires every Host stopped, backups and explicit permission.
Version 2.0.5+ reports a bounded `VAULT_BUSY.reason`: `IN_PROCESS`, or
`MODERN_`/`LEGACY_` with `LIVE`, `INVALID` or `UNVERIFIED`. These expose no PID,
token, path or raw exception. `LEGACY_LIVE` describes the compatibility ownership
marker, not proof of an old database format or identification of its process.
A visible Desktop quitting does not prove all older Hosts exited; inspect process
identities/start times without command arguments or credential-file reads, and
obtain permission before terminating verified obsolete Hosts.
Confirm the replacement with the native Vault status tool, not just an active
plugin row. Details and tested crash boundaries belong to the
[Vault core](../../plugins/dsh/secrets-vault/core/README.md).

Vault 2.0.6 replaces the ordinary dispose listener with an owned effect disposer.
Upgrading an already-active older Vault requires a full Host restart: native
unload did not invoke the old listener, so ownership and cleanup resources may
remain live. A working UI does not prove teardown works. Do not force-close or
unlock the Vault to bypass ownership or restart requirements.

If the old `profileDirectory` differs from the launcher-selected profile, keep
the complete plugin-owned directories intact until a separately authorized
migration. Moving an entire directory while both writers are stopped preserves
SQLite sidecars, Vault recovery files, permissions, and encrypted contents; do
not inspect secrets, reconstruct a database, or overwrite an existing destination.
Native package removal is not permission to delete user data. Keep a trusted old
SQLCipher runtime if legacy data still needs migration. The former
[private configuration generator](../../installer/dsh_local_bundle.py) remains
only for legacy explicit-path deployments, not the normal installation route.

## Interface languages

The plugins use DSH's native `locale` service: Russian for the `ru` selection,
English for every other language, without a separate preference. Each package's
locale dictionaries own its metadata and UI copy (for example, Vault's
[English](../../plugins/dsh/secrets-vault/locale/en.json) and
[Russian](../../plugins/dsh/secrets-vault/locale/ru.json) resources). Message Time
has metadata only; timestamp payloads remain language-neutral.

Analytics and Vault embed these dictionaries in their generated client bundles.
After changing translations or templates, rebuild before packaging:

```sh
node plugins/dsh/activity-analytics/build-client.mjs
node plugins/dsh/secrets-vault/build-client.mjs
node --test plugins/dsh/localization.test.mjs
```

The [shared build helper](../../plugins/dsh/build-locales.mjs) validates key and named
placeholder parity. It is development-only; installed clients need no translation
library, source checkout, or JSON network fetch. Native locale subscriptions
update visible strings; user-entered names and remote response content are not translated.

## Build release archives from a checkout

The maintained entrypoint is [install.py](../../install.py), which requires
Python 3.11 or newer on macOS or Linux. From the repository root, set
`PACKAGE_OUTPUT` to an absolute path outside the checkout and DSH home/profile
directories. Its parent must exist. Use a new output directory.

```sh
python3 -B install.py dsh package --surface desktop --output "$PACKAGE_OUTPUT"
```

The `--surface` value records whether the intended handoff is for Desktop or
CLI. The builder uses the Python standard library and writes the archives
locally. Native dependency resolution and activation happen later through DSH.
Replace or remove legacy private bundles that still supply a Vault `python`
setting through native management.

The [package builder](../../installer/dsh_package.py) stages declared runtime
files and produces deterministic npm-compatible archives. Its JSON report
includes each `mainframe-<plugin>-<version>.tgz` path, SHA-256, and native
handoff. The report leaves `profile_verified`, `composition_verified`, and
`runtime_verified` false. The Vault archive contains the standalone Node core.
Clipboard import requires macOS `pbpaste` and SSH uses supported local Unix
tools. Keep release archives outside the checkout and out of Git.

### Vault v2 transition and legacy data

For a profile that has never created a Vault, install v2 normally and create it
only in the private UI. No reset, file deletion, SQLCipher runtime or migration is
needed. The new encrypted store is `secrets-vault/vault.v2.json`; its recovery
sidecar is `vault.v2.json.recovery.json`. Back up both together while locked.

Existing SQLCipher `vault.db` or `vault.db.recovery.json` is not an empty Vault.
V2 refuses to initialize or unlock over legacy state and does not decrypt, modify,
rename, delete or automatically migrate it. Preserve the entire legacy directory,
including recovery sidecars, and a known-working old release/runtime. Roll back
through native management if access is needed; never run both generations at once.
A corrupt, empty or orphaned legacy file is not permission to reset the profile.

There is **no shipped legacy migration utility**. Node crypto cannot decrypt
SQLCipher files by itself. Migration can be a separately authorized optional
manual operation or a future private UI feature using a trusted SQLCipher-capable
reader, not an agent tool or automatic install step. Such a route must authenticate
the original password or recovery envelope, finish any interrupted legacy rekey,
read decrypted data only in private memory, validate every record/ID/timestamp and
agent-use grant, write an independently encrypted v2 candidate atomically, and
verify it after locking/reopening before a user-controlled cutover. Preserve the
untouched original and do not emit plaintext exports, credentials or recovery keys
into chat, arguments, environment or logs. Legacy files must remain outside the
active v2 location after an explicitly authorized cutover; installing v2 is not
that authorization. Until such a route exists, legacy users should remain on a
known-working old release rather than perform a destructive upgrade.

## Read-only planning and verification

```sh
python3 -B install.py dsh plan --surface desktop
python3 -B install.py dsh verify --surface desktop
```

These validate repository source only: exact inventory, file boundary, package
identity, declared runtime files, and hashes. They write no profile or adaptation
state and explicitly report `profile_verified=false` and
`composition_verified=false`; delivery/verification remain pending. Other
MAINFRAME components have no implemented mapping in this plugin adapter.
`apply`, `enable`, `disable`, `uninstall`, and `recover` remain native-manager
operations, not Python file transactions.

## Verification map

| Guarantee | Boundary / command | Acceptance |
| --- | --- | --- |
| Source boundary and planning | `python3 -B -m unittest tests.test_dsh_installer` | Synthetic homes; no native activation claim |
| Packed payload and checkout independence | `python3 -B -m unittest tests.test_dsh_package` | Deterministic archives, exact core payload, no interpreter provisioning or subprocess |
| Analytics behavior | Package-cwd `node --test *.test.mjs` | Synthetic SQLite data; not rendered/native acceptance |
| Message Time behavior | Package-cwd `node --test test.mjs` | Synthetic events |
| Session Collaboration waits and task metadata | Package-cwd `node --test *.test.js` | Synthetic services/storage only; no real session or native delivery claim |
| Vault UI/tool contracts | Package-cwd `node --test clipboard.test.mjs ui-contract.test.mjs recovery-ui.test.mjs` | Source/synthetic boundary, no real credentials |
| Private config-only generator | `python3 -B -m unittest tests.test_dsh_local_bundle` | No Python override, no profile file reads/writes |
| Vault encrypted persistence and recovery | Package-cwd `node --test core/core.test.mjs backend.test.mjs recovery.test.mjs recovery-host.test.mjs host.test.mjs` | Isolated synthetic files only; legacy refusal, no real user data |
| Native package activation and rendering | Current DSH profile/connected GUI | Observe separately; a registered slot is not a screenshot |

The existing Python unittest CI discovers adapter/build contract tests. Native
DSH GUI acceptance and packed Node persistence/recovery execution require separate
observed evidence; do not infer them from a successful archive build.
