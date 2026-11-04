# DSH source-plugin adapter

This is a maintained **source planning and native handoff** route, not a full
MAINFRAME global installer. It reuses the exact [inventory](../../ADAPTATION.example.json),
shared validation and adaptation-state semantics through [install.py](../../install.py)
and [installer/dsh.py](../../installer/dsh.py).

## Scope

The repository owns three original DSH source bundles:

| Source | Package | Copied version |
| --- | --- | --- |
| [Activity Analytics](../../plugins/dsh/activity-analytics/package.json) | `@mainframe/activity-analytics` | 1.2.0 |
| [Message timestamps](../../plugins/dsh/message-time/package.json) | `@mainframe/message-time` | 1.1.0 |
| [Secrets Vault](../../plugins/dsh/secrets-vault/package.json) | `@mainframe/secrets-vault` | 1.3.0 |

These are native DSH implementations, not generated copies of product-neutral
MAINFRAME skills. Codex, ZCode, MiniMax and Cline explicitly classify these three
plugin entries as unsupported on their own targets, without delivering them or
changing their existing component mappings.

## Read-only entrypoint

From the MAINFRAME repository root:

```sh
python3 -B install.py dsh plan --surface desktop
python3 -B install.py dsh verify --surface desktop
```

Use `--surface cli` only as the requested surface selection, not proof of CLI
compatibility. Both actions validate repository source and print the same handoff;
`verify` succeeds for **source validation only**. The report explicitly says
`verification_scope=repository-source-only`, `profile_verified=false`,
`composition_verified=false` and keeps
all delivery/verification rows pending. It writes no adaptation file, ownership
receipt, lock, profile configuration, runtime or package installation. It does
not inspect the selected home, active profile, credentials or session history.

`apply`, `enable`, `disable`, `uninstall` and `recover` are rejected. Their native
owner is DSH's `plugin_manager`; a Python file transaction cannot roll back that
profile-level lifecycle. Other MAINFRAME components remain pending with the
explicit limitation that this adapter has not implemented their DSH mapping.
That is not a claim that DSH cannot support skills, roles or hooks.

## MAINFRAME namespace and continuation boundary

Repository packages use `@mainframe/*`; the scope identifies their MAINFRAME
ownership, not an npm publication or installation location. Manifest names,
Cordis package references and Client module ids use the same scope. Loader row
ids, services, storage keys, data paths and source directories are unchanged.
The copied versions above are retained; this is a package-identity change, not
proof of a runtime upgrade.

Previously running packages were named `@local/activity-analytics`,
`@local/message-time` and `@local/secrets-vault`, linked to the original workspace
sources. This repository rename does not rename those packages, change their
configuration, install a second copy, or migrate any data. The native profile
must be inspected afresh: this document is not evidence of its current state.

For a new project conversation, start with this guide and the repository's
[development instructions](../../AGENTS.md). The source import and namespace
rename are complete. Remaining work, only after an explicit profile switchover
request, is to establish supported native configuration, preserve existing
profile/data ownership, replace the old identities without concurrent duplicate
bindings, and verify activation and rendered behavior. Follow the prerequisites
below; do not blindly install the new scope alongside the old one. Native
activation and Vault's external SQLCipher runtime remain unverified.

## Native installation/update handoff

Only perform this stage for an explicit profile installation/update request.
The current source import does **not** retarget existing linked installations.

1. Use `plugin_manager` listing actions to identify exact installed bundles and
   entries in the selected DSH profile. Preserve unrelated bundles and settings.
2. Inspect the current DSH tool schema and relevant plugin Config contracts.
   Use supported native plugin configuration for target-local values, not direct
   edits to profile manifests or profile patch layers. If configuration cannot
   be safely supplied with the installed native interface, stop before activation
   and report that concrete prerequisite; do not install an unconfigured bundle.
3. The report supplies absolute local directory install targets. Local installs
   may link the source: keep the repository at that path. Native lifecycle goes
   through `plugin_manager`, never a subprocess package manager in the profile.
4. Analytics and Vault need the actual selected `profileDirectory` unless the
   Host provides `DSH_PROFILE_DIR`. Reusable patches intentionally omit machine
   paths. Do not guess a desktop profile or copy an old machine's configuration.
5. Vault additionally needs an explicitly provisioned/configured external Python
   with `sqlcipher3` and SQLCipher. No venv, database, recovery envelope, password,
   key or usage authorization is included or migrated. See its
   [runtime/security documentation](../../plugins/dsh/secrets-vault/README.md).
   Analytics requires usable `node:sqlite`; see its
   [storage documentation](../../plugins/dsh/activity-analytics/README.md).
6. Inspect the actual linked source or packed archive boundary before install.
   Linked installs do not apply the package manifest's `files` filter. The DSH
   source adapter rejects unexpected files/directories and symlinks rather than
   opening them. Tests/build source are repository support; runtime package
   payload is declared in each manifest. Do not introduce local environments,
   probes or secrets into these directories.
7. Verify native discovery and enabled/active state separately from successful
   installation. Then check rendered UI and plugin-specific behavior on the
   requested surface. Source hashes and tests are not acceptance evidence.
   Never exercise real vault credentials as a development probe.

Existing original source directories and profile data must remain intact until
a separately authorized, verified switchover. Removing a plugin is distinct from
deleting user analytics/vault history; preserve that history.

## Verification map

| Guarantee | Boundary / command | Route / acceptance |
| --- | --- | --- |
| Exact source inventory, link integrity | `python3 -B -m unittest tests.test_repository` | Local + existing repository CI; all assertions pass |
| Read-only plan, honest status, source rejection and CLI options | `python3 -B -m unittest tests.test_dsh_installer` | Local + existing unittest CI; no profile writes or installed claims |
| Existing four adapters preserve behavior and skip DSH rows | `python3 -B -m unittest tests.test_dsh_legacy` | Disposable homes locally + existing CI; update/convergence/removal and foreign files preserved |
| Analytics source behavior | Analytics package-cwd `node --test *.test.mjs` | Local synthetic data; not native acceptance |
| Message-time source behavior | Message-time package-cwd `node --test test.mjs` | Local synthetic events; not native acceptance |
| Vault source/UI contracts | Package-cwd `node --test clipboard.test.mjs ui-contract.test.mjs recovery-ui.test.mjs` | Local synthetic/source-only boundary; no worker or credentials |
| Vault encrypted persistence, native runtime and GUI | Explicit synthetic-runtime integration / interactive native checks | Separate acceptance task; pending, not inferred from source tests |

The existing Python unittest CI automatically discovers the adapter tests. Native
DSH GUI/SQLCipher/Node plugin acceptance is not added to CI by this source import.
