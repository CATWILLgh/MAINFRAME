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
observer also preserves permission-action and nested pattern order because
OpenCode applies the last matching rule.

Configuration planning uses the same immutable inspection as observation and
does not read the host again. Configuration and MCP observers share one
location-keyed read snapshot, so a file used by both cannot represent two
different moments in one preview. The TUI presents semantic configuration intent
separately from the executable filesystem plan: add, update, remove a
registry-proven managed entry, or stop managing a user-changed or deleted
entry. A resource is the atomic planning group, so the OpenCode configuration
file and ownership registry never appear as independent operations. Apply
stays unavailable until every supported configuration strategy has complete
ownership and deselection semantics and the remaining executor activation
gates pass.

Codex hook trust is an adapter-local external prerequisite. The release
contract names the desired hook source, while the observer asks Codex's
read-only `hooks/list` interface for the effective state. Ready requires all
of the following: the desired hook artifact is already managed exactly for
the selected release, the response names the resolved Codex hook target,
warnings and errors are absent, the non-empty semantic handler set matches
the verified release source exactly, and every handler is enabled and trusted
or managed. File presence alone is never evidence of trust. MAINFRAME never
reads or writes Codex's persisted `hooks.state`.

External manual actions and inspection notices are separate from executable
configuration changes and unresolved ownership issues. They never enter a
prepared transition or executor journal. Deselection suppresses them without
revoking external state. An unavailable or incompatible Codex executable
produces a non-blocking notice rather than a misleading `/hooks` instruction.

## MCP onboarding is catalog-driven and adapter-owned

MAINFRAME may ship a verified catalog of MCP server descriptions and adapter
recipes, but an MCP connection is always an explicit user choice. The user
selects one connection profile and then independently selects the adapters
that should receive it. Each adapter owns and observes only its own projected
configuration; no adapter discovers an MCP server by reading another
adapter's configuration.

A connection profile is one valid combination, not a Cartesian product of
independent transport and authentication lists. It records the client-facing
transport, endpoint or command, transport authentication, optional external
service credential, credential placement, compatible adapters, and the
source date that verified the recipe. This distinguishes an HTTP server that
authenticates the MCP client from a local stdio process that needs no MCP
transport authentication but may accept an API key for the external service
it calls.

The first onboarding scope supports profiles with no credential and profiles
with an API key. OAuth implementation is deferred until a selected server
requires it. OAuth-only profiles remain visible so the catalog does not imply
false compatibility, but they are marked unsupported and cannot enter an
installation plan; the TUI explains which capability is missing.

The catalog card explains the server's purpose and shows its publisher,
authoritative source, repository link, license, supported connection profiles,
credential requirement, and last verification date. Repository stars may be
shown as optional time-stamped popularity metadata. They are never a security
or trust signal, never gate installation, and their absence or refresh failure
must not block an otherwise verified offline catalog entry.

Credentials never enter the release, project files, previews, logs, or
executor journal. The TUI may collect an API key through masked input and
store it in the neutral credential store only after the selected adapter
recipe proves that it can consume a reference without leaking the value. If
an adapter cannot do so safely, that profile is unsupported for that adapter
instead of embedding the key in clear text.

Context7 is the first reference catalog entry. Its
[maintained repository](https://github.com/upstash/context7#installation)
describes an API key as recommended for higher rate limits rather than a
universal prerequisite, while its
[client-specific recipes](https://context7.com/docs/resources/all-clients)
commonly include one.

The catalog therefore models keyed and unkeyed profiles explicitly and tests
the selected profile instead of claiming that every Context7 installation
requires a key. Shared local process hosting is a separate runtime concern;
direct stdio remains the default until a gateway proves real multi-client
multiplexing and safe lifecycle ownership.

The first implemented catalog milestone is intentionally read-only. The
release index verifies a separate bounded MCP catalog by path and SHA-256, and
the TUI records a choice between environment selection and the final preview.
It does not yet collect a key or publish adapter configuration. Context7's
keyless remote profile is verified for Claude Code, Codex, OpenCode, and
Antigravity 2.x. Its keyed remote profile is verified for Claude Code, Codex,
and OpenCode; Antigravity 2.x is explicitly unsupported until a plaintext-free
secret reference is proven. Optional GitHub stars are fetched asynchronously,
kept only in memory, and discarded when stale or unavailable.

The second read-only milestone gives keyless Context7 exact OpenCode, Claude
Code, and Codex projections. Bundle schema version 2 links each projection to the catalog
server and profile instead of repeating the endpoint or authentication data.
The TUI can therefore classify each adapter-local Context7 entry as an
addition, update, managed removal, user-owned conflict, relinquished ownership,
or already ready.

OpenCode owns only `mcp.context7` in its own configuration and keeps MCP
ownership separate from its permission registry. Claude Code uses the verified
user-scope `~/.claude.json` contract, but the codec admits only the exact
`mcpServers.context7` entry; the release component does not receive general
access to the home root. Its ownership registry lives separately under
`~/.claude/mainframe/` and is never shared with OpenCode. Codex observes only
`mcp_servers.context7` in its own global `config.toml` through a strict TOML
codec and keeps its ownership registry under its own `mainframe/` directory.
The codec rejects invalid or redefined TOML and never treats temporal or
non-finite TOML values as equivalent JSON ownership state. Antigravity remains
descriptive until its own configuration codec and root satisfy the same
contract.

Every loaded projection is revalidated before host inspection. An unsafe state
in one selected adapter makes the combined plan blocking without hiding valid
intents for its siblings; an unselected adapter's state cannot block the active
adapter. The neutral preview never treats one adapter's state as belonging to
another. Preview contains no configuration bytes, secret input, or Apply
path. A separate preparation boundary may derive immutable after-images from
the same snapshots without exposing them in the TUI.

The adapter capability boundary was verified on 2026-07-17 against the
[Claude Code MCP contract](https://code.claude.com/docs/en/mcp),
[Codex MCP contract](https://developers.openai.com/codex/mcp/),
[Codex configuration contract](https://developers.openai.com/codex/config-reference/),
[OpenCode MCP contract](https://opencode.ai/docs/mcp-servers/), and
[Antigravity MCP contract](https://antigravity.google/docs/mcp).

Before execution, the immutable inspection can materialize a private prepared
plan without writing. It preserves complete user JSON, composes non-overlapping
resources sharing one physical file, and groups each configuration with its
ownership registry. Every file mutation is bound to exact captured bytes,
mode, device, and inode; missing files use an explicit absence precondition.
Prepared bytes remain outside the executor journal. Any unresolved issue,
unsupported changed strategy, incomplete snapshot, or target collision fails
the whole preparation with no partial result.

Codex Context7 preparation never reserializes the user's complete TOML file.
MAINFRAME appends one deterministic, versioned block and recognizes it later
only when both the adapter-local ownership registry proves the block format
and the exact block remains the file suffix. Update and removal validate the
complete TOML semantics before and after the byte-scoped change; any edited
marker, legacy semantic-only registry entry, marker-like multiline string, or
unrelated semantic drift fails closed. The single-block format admits one
Codex MCP projection; a release with more is rejected until
[#38b9fb12](tickets/38b9fb12-compose-codex-mcp-managed-region.md) replaces it
with one deterministic multi-entry region.

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

Configuration changes participate in the same lock and transaction as link and
directory changes. Journal schema version 2 records only targets, content
digests, modes, file identities, and private names; configuration bytes remain
in the immutable prepared plan held by the process. The decoder accepts only
the exact prior unversioned journal shape and upgrades it as a link-only
transaction, so an interrupted legacy operation remains recoverable.

Before staging, each configuration target is rebound to the exact current
parent and before-image captured during preview. Staged bytes are written with
exclusive creation under a reserved writing name inside an identity-bound
`0700` sibling directory, synchronized, and atomically promoted to the staged
name at owner-only mode. Interrupted partial writes are discarded only from
that reserved private entry after type, ownership, link-count, mode, and
identity checks. Every target parent must be on the supported local-filesystem
list and pass real no-replace and exchange renames inside that private
directory before any public link or configuration name is changed.

Creating a configuration file uses a no-replace rename. Replacing one uses an
atomic exchange, retaining the previous inode inside the private directory.
Each publication boundary is saved independently, configuration rollback runs
in reverse order before link and directory rollback, and committed recovery
removes only entries whose identities still match the journal. Probe remnants
from an interruption are removed only when their type, ownership, mode,
identity, and protocol-defined content or interrupted-write prefix are
recognized; any foreign entry fails closed.

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
