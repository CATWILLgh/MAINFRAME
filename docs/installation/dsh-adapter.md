# DSH plugin packages

MAINFRAME owns three native DSH plugins: [Activity Analytics](../../plugins/dsh/activity-analytics/README.md),
[Message Time](../../plugins/dsh/message-time/package.json), and
[Secrets Vault](../../plugins/dsh/secrets-vault/README.md). These are DSH implementations,
not generated copies of product-neutral MAINFRAME skills. Other product adapters
classify these entries as unsupported without installing them.

## User installation and updates

Install **packed `.tgz` packages**, not repository directories. A directory install
is a development link: deleting the checkout breaks it. A packed install is an
independent copy managed by DSH. No Local Deployment bundle is needed.

1. Obtain the three packages built for the destination OS/architecture. Keep the
   versioned archives in persistent user storage **outside the checkout**. The
   Vault archive includes its own Python/SQLCipher runtime; end users do not need
   Python, Homebrew, uv, compiler tools, or an activation package.
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
directories. `profileDirectory` and Vault's `python` remain advanced compatibility
overrides. Source/unrecognized layouts without explicit context fail closed.
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
holds an exclusive worker lock; an obsolete Host can keep the new worker unavailable
even after the visible Desktop restarts. Identify the lock-owning process and its
parent without reading the database; obtain permission before stopping that older
Host. Never delete the lock file or bypass the lock. Confirm the replacement with
the native Vault status tool, not just an active plugin row.

If the old `profileDirectory` differs from the launcher-selected profile, keep
the complete plugin-owned directories intact until a separately authorized
migration. Moving an entire directory while both writers are stopped preserves
SQLite sidecars, Vault recovery files, permissions, and encrypted contents; do
not inspect secrets, reconstruct a database, or overwrite an existing destination.
Native package removal is not permission to delete user data. Verify the new
runtime before removing an old external Python environment. The former
[private configuration generator](../../installer/dsh_local_bundle.py) remains
only for legacy explicit-path deployments, not the normal installation route.

## Build release archives from a checkout

The maintained entrypoint is [install.py](../../install.py). From the repository
root, select the current surface and a **new absolute output directory outside
the checkout** whose parent already exists:

```sh
python3 -B install.py dsh package --surface desktop --output "$PACKAGE_OUTPUT"
```

Building Vault requires `uv` on PATH and network access. The build provisions
standalone CPython **3.12.12** and a binary-only **sqlcipher3 0.6.4** wheel into a
separate build tree, verifies an in-memory SQLCipher connection, and records
nonsecret runtime version/target metadata. No existing venv, user Python,
credential database, recovery envelope, or DSH profile is opened. Provisioning
uses [uv's standalone Python distribution](https://docs.astral.sh/uv/guides/install-python/)
and [sqlcipher3's bundled-SQLCipher wheel](https://pypi.org/project/sqlcipher3/0.6.4/).
Upstream notices/licenses stay in the runtime payload. A failed runtime build
leaves only its isolated build directory for diagnosis.

For an already prepared standalone runtime, use `--vault-runtime` pointing at
its root (the directory containing `bin/python3.12`), not a venv. The supplied
runtime is executable code and must come from a trusted build. Package creation
checks its layout; functional acceptance still requires running the packed
runtime in an isolated fixture. Do not copy an existing user's environment.

The current build route targets the local macOS arm64/x64 or glibc Linux arm64/x64
platform when matching upstream binary wheels exist. Vault's clipboard adapter
currently requires macOS `pbpaste`; Linux credential-entry/HTTP/SSH support is
not proof of Linux clipboard integration. Windows and musl Linux are not
supported by this release route. Build separately on each target platform;
archives are not cross-platform merely because Host code is JavaScript.

[The package builder](../../installer/dsh_package.py) stages only declared runtime
files plus the separately supplied runtime, writes npm-compatible archives and
SHA-256 hashes, and never changes a profile. Runtime symlinks must resolve inside
that runtime and are materialized as regular files so npm cannot silently omit
required executables/libraries. Tests, local data, environments, and checkout
metadata are not plugin source payload. Runtime directories stay outside source
and archives are not committed to this public repository.

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
| Standalone runtime provisioning | `python3 -B -m unittest tests.test_dsh_runtime` | Pinned commands, fail-closed output/platform; synthetic subprocesses |
| Packed payload and independent install | `python3 -B -m unittest tests.test_dsh_package` | Archive inspection/extraction; synthetic runtime fixtures |
| Analytics behavior | Package-cwd `node --test *.test.mjs` | Synthetic SQLite data; not rendered/native acceptance |
| Message Time behavior | Package-cwd `node --test test.mjs` | Synthetic events |
| Vault UI/tool contracts | Package-cwd `node --test clipboard.test.mjs ui-contract.test.mjs recovery-ui.test.mjs` | Source/synthetic boundary, no real credentials |
| Vault encrypted persistence and recovery | Isolated packed-runtime integration tests | Synthetic database only; never real user data |
| Native package activation and rendering | Current DSH profile/connected GUI | Observe separately; a registered slot is not a screenshot |

The existing Python unittest CI discovers adapter/build contract tests. Native
DSH GUI acceptance and platform-specific packed SQLCipher execution require
separate observed evidence; do not infer them from a successful archive build.
