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

Configuration ownership is explicit release data. Static JSON ownership uses
non-overlapping RFC 6901 pointers. OpenCode permission ownership instead uses a
versioned map-entry descriptor that binds the desired permission map to the
adapter-local `opencode.json.mainframe-permissions.json` registry. Observation
computes the same safe fixed point as the compatibility generator: absent
state never adopts matching user entries, changed or deleted managed entries
become permanent tombstones, and unrelated entries remain user-owned. The
observer also preserves nested permission-rule order because OpenCode applies
the last matching pattern. The
configuration file and registry are one logical state transition; Apply stays
unimplemented until the executor can journal, publish, and recover both files
together.

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

The `mainframe` launcher is the explicit activation pointer, not a request to
search the release store. Its symbolic-link target names one exact stored
release and digest. When invoked without arguments, the executable derives its
release root from its own resolved path, reopens that exact release, validates
the index, and then starts the TUI. It never guesses the newest release.
Several complete releases may coexist without making startup ambiguous.

This is product-level immutability, not an operating-system security boundary:
another process running as the same user can still alter stored files. Every
future plan and application must therefore reopen and fully validate the
selected version immediately before use, then bind the result to both the
release ID and exact release-index digest.

Link changes use a recoverable sibling workspace in the target parent. The
journal records the private directory name and inode before publication, then
records the staged link inode. Installation publishes that exact staged link
with a no-replace rename. Removal moves the exact managed link into the private
workspace with a no-replace rename so rollback retains the original inode.
MAINFRAME never unlinks a public target name. A committed transaction removes
only verified private entries before it removes its journal; an interrupted
transaction performs the inverse renames and can safely retry each step.

Every parent and private directory is opened descriptor-relatively without
following symbolic links and checked against its recorded identity. Detected
concurrent changes before a namespace transition fail closed. The operating
systems do not atomically bind a no-replace rename's source name to a previously
observed inode. Another same-user writer that does not share MAINFRAME's
transaction lock can therefore replace the source in that narrow interval; the
replacement inode is retained rather than unlinked, but its public name may be
moved.

The Go executor and every mutating `install.sh` path share the persistent
`${XDG_STATE_HOME:-$HOME/.local/state}/mainframe/transaction.lock`. The
compatibility installer takes the same non-blocking BSD lock through macOS
`lockf` or Linux `flock`, never removes the lock file, and holds its descriptor
through all synchronous child commands. A read-only dry run and a failed
install-source preflight create no lock state; uninstall locks before its first
mutation. If the shell exits while a child still holds the inherited
descriptor, exclusion lasts until that final child exits, favoring delayed
availability over concurrent mutation.

Missing target parents are not created implicitly by a link operation. The
executor derives required directories from the saved plan and configured
roots, records every missing path before the first write, and creates them
parent-first through hidden sibling directories and no-replace renames. The
journal binds each path to a canonical existing anchor, the configured
physical root, the exact parent and created-directory identities, and the
requested mode.

Rollback processes links first and directories child-first. It moves only the
exact created directory, checks emptiness before and after the move, and
restores a directory that another process populated. If restoration collides,
the populated inode remains retained under its journaled private name and a
later retry returns it to the public name when that name becomes free. Existing
directories are never changed or claimed.

The installer creates every missing managed directory with mode `0700` and
never changes an existing directory's mode. This is a deliberate same-user
policy, consistent with the XDG requirement to create missing destination
directories as `0700`: every shipped runtime and command consumes its target
through the installing user's account, and no supported target requires
cross-user traversal. A root-specific mode may be introduced only alongside a
concrete consumer that needs a different access boundary. Native Linux
lifecycle execution remains required before the public Apply action can be
enabled; that check stays in
[#20e75df1](tickets/20e75df1-model-managed-target-directories.md).
Before persisting managed-directory intents, the executor reads the inherited
process mask in an isolated child process. A mask that removes any required
`0700` owner bit is rejected without changing the parent process or staging a
managed target directory.

Every component must pass an isolated-install scenario in which the other
runtime directories do not exist. Lifecycle operations must preserve
user-owned files, affect only the selected component and explicit neutral
dependencies, and remain safe to repeat.

`install.sh` remains a compatibility path until the TUI covers the same
observable behavior. Compatibility does not exempt it from the isolation
boundary: temporary implementation gaps are tracked explicitly and are not a
reason to encode cross-runtime access into the release model.
