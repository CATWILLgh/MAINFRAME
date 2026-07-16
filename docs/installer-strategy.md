# Installer and runtime isolation strategy

This document is the normative architecture for the MAINFRAME release, TUI,
and the eventual replacement of `install.sh`. The legacy installer may remain
available during the transition, but new work must move toward this contract
and must not introduce new cross-runtime dependencies.

## Source sharing is not runtime sharing

`core/` is the neutral source of truth for behavior shared by Claude Code,
OpenCode, Codex, and Antigravity 2.x. Each adapter may transform that source
for its runtime, but the resulting runtime bundle is closed: it contains every
MAINFRAME artifact that runtime needs to operate.

A runtime must not read or execute MAINFRAME files from another runtime's
configuration, data, cache, plan, memory, hook, or plugin directories. Copying
neutral source into several bundles at build time is intentional. Sharing one
installed runtime copy at execution time is forbidden.

## Runtime isolation and delivery independence

These are separate guarantees and both are required:

- **Runtime isolation:** after installation, each adapter reads only its own
  runtime roots and the explicit neutral interfaces listed below.
- **Delivery independence:** a user can install, update, repair, reconfigure,
  or remove one runtime without installing or changing another runtime.

The release manifest enforces the first boundary for every `install_unit`,
`legacy_artifact`, and managed `resource`:

| Component | Roots it owns |
|---|---|
| `claude-code` | `claude-config` |
| `codex` | `codex-config` |
| `opencode` | `opencode-config` |
| `antigravity-2` | `antigravity-config`, `antigravity-data` |
| `credential-tools` | `user-bin`, `credentials-config`, `home` |
| `mainframe-cli` | `user-bin` |

Unknown components and roots are contract errors. The `home` allowance is
limited to `.bashrc`, `.profile`, and `.zshenv`; it is not a general route into
runtime directories. Adapter components may depend only on
`credential-tools` and `mainframe-cli`, while those neutral components have no
component dependencies. Runtime bundles therefore cannot use either a target
path or a dependency edge as a route into another runtime's files.

## Explicit neutral interfaces

Cross-component access is allowed only through a separately owned, documented
interface:

- `mainframe-cli` owns the `mainframe` launcher in `user-bin`.
- `credential-tools` owns the `secret` launcher, the credentials store, and
  the shell integration required to load that store.

Plans, memory, telemetry, feedback, permissions, hooks, skills, agents, and
runtime configuration are not neutral interfaces. Every adapter packages and
stores its own versions. Each adapter also seeds its own editable credentials
index while the secret store and `secret` command remain neutral. Migration
code may inspect legacy locations belonging to the same runtime, but must not
discover state through another runtime.

## Permission capabilities must be stated honestly

The TUI presents the protection each runtime can actually provide. A control
must be labelled as one of:

- enforced by the runtime;
- enforced by a MAINFRAME hook;
- advisory only;
- unsupported.

Adapters may project the same neutral policy where capabilities overlap, but
must not claim equivalent enforcement when the runtimes expose different
permission or hook surfaces. Installation remains available when a capability
is unsupported; the limitation is shown before applying the change.

## Release and TUI responsibilities

Release builders produce immutable, self-contained component bundles from
`core/` plus one adapter. The TUI consumes only the indexed release contract;
it does not infer ownership from repository paths or reach into a sibling
bundle at runtime.

Complete local releases are imported into
`$XDG_DATA_HOME/mainframe/releases/<release-id>/<index-sha256>/`, with
`~/.local/share` as the XDG fallback. Import copies through descriptor-relative
no-follow traversal, validates the closed staged tree, and publishes by
platform-native no-replace rename. MAINFRAME never overwrites or removes a
published version. There is intentionally no mutable `current` pointer.

This is product-level immutability, not an operating-system security boundary:
another process running as the same user can still alter stored files. Every
future plan and application must therefore reopen and fully validate the
selected version immediately before use, then bind the result to both the
release ID and exact release-index digest.

Every component must pass an isolated-install scenario in which the other
runtime directories do not exist. Lifecycle operations must preserve
user-owned files, affect only the selected component and explicit neutral
dependencies, and remain safe to repeat.

`install.sh` remains a compatibility path until the TUI covers the same
observable behavior. Compatibility does not exempt it from the isolation
boundary: temporary implementation gaps are tracked explicitly and are not a
reason to encode cross-runtime access into the release model.
