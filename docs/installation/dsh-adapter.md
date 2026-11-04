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
[development instructions](../../AGENTS.md). Native profile state is not repository
state: inspect it for each explicitly requested switchover. The maintained
[private bundle generator](../../installer/dsh_local_bundle.py) supplies local
configuration without adding user paths to source or directly editing profile
files. Its synthetic tests do not establish native activation, rendered behavior,
or Vault runtime compatibility. Follow the prerequisites below; do not install
the new scope active alongside the old one.

## Native installation/update handoff

Only perform this stage for an explicit profile installation/update request.
The current source import does **not** retarget existing linked installations.

1. Use `plugin_manager` listing actions to identify exact installed bundles and
   entries in the selected DSH profile. Inspect the current native tool schema
   and plugin configuration contracts. Preserve unrelated bundles and settings.
   Never write the profile manifest or patch layers, or run a package manager in
   the profile. A failure to supply configuration safely is a stop condition,
   not permission to activate unconfigured source bundles.
2. Confirm the selected profile directory explicitly; do not guess a desktop
   profile or copy another machine's configuration. Provision Vault's external
   Python with `sqlcipher3` and SQLCipher separately. No venv, database, recovery
   envelope, password, key or usage authorization is included or migrated. See
   Vault's [runtime/security documentation](../../plugins/dsh/secrets-vault/README.md).
   Analytics requires usable `node:sqlite`; see its
   [storage documentation](../../plugins/dsh/activity-analytics/README.md).
3. Inspect the linked source or packed archive boundary before installation.
   Linked installs do not apply the manifest's `files` filter. The read-only DSH
   source adapter rejects unexpected source entries and symlinks before opening
   them. Keep local environments, probes and secrets out of source directories.
   Install the Analytics and Vault source directories supplied by the source
   report separately with `plugin_manager`, `action: install_bundle`, and
   **`enabled: false`**. They supply resolvable plugin code, not active rows.
   Keep linked sources at their installed locations.
4. Generate the private configuration-only bundle as described below. Keep it
   outside this repository, the selected profile and DSH home. Its manifest has
   no dependency or install scripts; it does not copy Host code or provision a
   runtime. Install it first with `plugin_manager`, `action: install_bundle`,
   `enabled: false`, using its absolute output directory as `target`.
5. Before enabling the generated `@mainframe/local-deployment`, disable the old
   `@local/activity-analytics` and `@local/secrets-vault` bundles using exact
   identifiers obtained from native listing. **Keep the corresponding
   `@mainframe/*` source bundles disabled**: their insert rows use the same ids.
   Then enable only the generated deployment bundle with `set_bundle`. It inserts
   the configured `activity-analytics` and `secrets-vault` rows. Installing code
   successfully does not prove that disabled-source packages resolve from this
   activation bundle; observe native activation and diagnose resolution failures.
   If activation fails, disable the generated bundle before restoring the old
   bundles through native lifecycle operations; never enable both generations.
6. Message timestamps are not configured by this two-row deployment bundle.
   If switching that component too, disable `@local/message-time` before enabling
   its separate `@mainframe/message-time` source bundle. Preserve its existing
   state when that switchover is not requested.
7. Verify discovery, enabled state and active rows separately from installation.
   Check rendered metadata/icons and plugin behavior on the requested surface.
   Successful generation or source tests are not native acceptance. Never
   exercise real vault credentials as a development probe.

### Generate private activation configuration

From the repository root, supply three explicit **absolute**, nonsecret paths
through local shell variables (do not place real values in repository examples):

```sh
python3 -B -m installer.dsh_local_bundle \
  --output "$MAINFRAME_LOCAL_BUNDLE" \
  --profile-directory "$SELECTED_DSH_PROFILE_DIRECTORY" \
  --vault-python "$EXTERNAL_VAULT_PYTHON"
```

The output parent must already exist. Generation rejects output inside the
resolved repository, selected profile or DSH home (`DSH_HOME`, otherwise
`~/.dsh`), and rejects overlapping ancestor outputs too. It refuses symlinks in
output/profile paths and refuses a nonempty output. The Python argument is
serialized without resolving or inspecting it, so a venv interpreter symlink
retains its environment; supplying it does not prove it works. No profile
configuration, database, credential or runtime file is opened, and no Python
interpreter is executed by the generator.

The generated private package exports English/Russian metadata and original SVG
artwork alongside a JSON-compatible YAML insert patch. Only that patch carries
the local profile/Python paths. Bundle directories have mode `0700`, files `0600`;
creation stages a complete sibling tree and publishes with one atomic rename.
Only owned staging directories are eligible for failure cleanup. The generator
creates no parent directories and does not modify their permissions. Keep the
whole output private, do not commit or publish it, and retain it while linked.
`private: true` prevents npm publication but is not an access-control boundary.

### Updates and removal

Update source code with native `install_bundle` **`enabled: false`** again; an
update must not re-enable a source bundle. Retain the configured deployment
bundle as the sole Analytics/Vault activation owner. Honor native restart or
pending-application results before claiming updated behavior. To change local
paths, generate into a new empty private output, disable the current deployment,
then replace its installation through `plugin_manager` using the same package
identity; keep it disabled until the replacement is ready. Restore the prior
bundle through native lifecycle operations if replacement fails. Do not rewrite
an installed linked directory in place or edit profile manifests/patches.

To remove activation, disable/remove the generated bundle through native
`plugin_manager`; remove disabled source bundles separately only when no longer
needed. Package removal does not authorize deleting analytics or vault data.

Existing original source directories and profile data must remain intact until
a separately authorized, verified switchover. Removing a plugin is distinct from
deleting user analytics/vault history; preserve that history.

## Verification map

| Guarantee | Boundary / command | Route / acceptance |
| --- | --- | --- |
| Exact source inventory, link integrity | `python3 -B -m unittest tests.test_repository` | Local + existing repository CI; all assertions pass |
| Read-only plan, honest status, source rejection and CLI options | `python3 -B -m unittest tests.test_dsh_installer` | Local + existing unittest CI; no profile writes or installed claims |
| Private config-only generation, output boundaries, permissions and failure cleanup | `python3 -B -m unittest tests.test_dsh_local_bundle` | Disposable filesystem locally + existing unittest CI; no real profile/runtime access or native activation claim |
| Existing four adapters preserve behavior and skip DSH rows | `python3 -B -m unittest tests.test_dsh_legacy` | Disposable homes locally + existing CI; update/convergence/removal and foreign files preserved |
| Analytics source behavior | Analytics package-cwd `node --test *.test.mjs` | Local synthetic data; not native acceptance |
| Message-time source behavior | Message-time package-cwd `node --test test.mjs` | Local synthetic events; not native acceptance |
| Vault source/UI contracts | Package-cwd `node --test clipboard.test.mjs ui-contract.test.mjs recovery-ui.test.mjs` | Local synthetic/source-only boundary; no worker or credentials |
| Vault encrypted persistence, native runtime and GUI | Explicit synthetic-runtime integration / interactive native checks | Separate acceptance task; pending, not inferred from source tests |

The existing Python unittest CI automatically discovers the adapter tests. Native
DSH GUI/SQLCipher/Node plugin acceptance is not added to CI by this source import.
