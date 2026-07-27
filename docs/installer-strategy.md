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
  the shell integration required to load that store. It is also the only
  component allowed to own user credential-instance metadata.

Plans, memory, telemetry, feedback, permissions, hooks, skills, agents, and
runtime configuration are not neutral interfaces. Every adapter packages and
stores its own versions. The current compatibility release still seeds
adapter-local editable credential indexes. New code must not extend that
legacy arrangement; the central credential contract below replaces it with
one neutral catalog owned by `credential-tools`. Until an explicit migration
is implemented, existing adapter-local indexes remain untouched and are not
treated as authoritative. Migration code may inspect legacy locations
belonging to the same runtime, but must not discover state through another
runtime.

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

## Local diagnostics reuse the DEV instrumentation

The first TUI screen is a settings overview rather than the first step of a
one-way wizard. It opens environments, MCP integrations, and additional tools
as separate sections. Every section returns to the overview. Only the combined
plan can eventually apply their desired state, and the current preview-only
build says so before the user opens any section.

Local diagnostics reuse the mechanisms already proven by `install.sh --dev`:

- `telemetry.py` and `_hooklib.log_event` produce metadata rows in a local
  SQLite database;
- `harness-feedback` writes structured local friction reports;
- `build_hub_page.py` provides reusable static display and query groundwork.

The old `--dev` flag remains an all-in-one Claude Code development shortcut
until the TUI reaches apply parity. The TUI preserves the same hierarchy:
`DEV` is the parent choice, and `harness-feedback` is an optional capability
inside it. The feedback choice stays hidden while `DEV` is off, and the
lifecycle rejects `feedback=true` with `events=false`. Both are off unless the
user chooses them, neither sends data over the network, and neither is useful
until at least one environment is selected.

The TUI may present one concise choice across the selected environments, but
materialization stays adapter-owned. Each selected adapter receives its own
activation state, event database, feedback receiver, and reports under its own
configuration or data root. One adapter never reads another adapter's
diagnostic data. The neutral `mainframe` command may aggregate those stores for
the user because it owns the management interface; aggregation does not turn
the stores into a shared runtime dependency.

A database path is only a locator, never consent. Adapter launchers must not
set an override that implicitly creates a telemetry directory. Existing data
is preserved when collection is disabled. Before diagnostics enter an
executable plan, the lifecycle needs an explicit adapter-local activation
resource, observation of current state, bounded retention, and `0700`/`0600`
directory and file permissions.

The activation contract starts with a versioned adapter-local
`mainframe/diagnostics.json` document. Schema version 1 stores boolean `events`
and `feedback` fields, but valid desired state has the invariant
`feedback => events`. Missing, invalid, unreadable, foreign, or disabled state
fails closed; path overrides remain locators only. Runtime writers bind their
leaf directories before publication, use `0700` for data directories and
`0600` for databases and reports, and never remove existing diagnostic history
while disabling collection.

Bundle schema version 5 keeps the version-4 activation resource and adds an
optional feature identifier to ordinary install units. Every adapter ships a
dormant `dev.harness-feedback` unit in the authenticated release: Claude Code
targets the separate `mainframe-dev` plugin, while Codex, OpenCode, and
Antigravity target their own skill roots. A dormant unit may exist in the
release cache, but the planner installs it only when feedback is enabled and
removes an owned installed unit when feedback is disabled. It never affects
the base installed status of an adapter.

The release exemplar proves that the adapter ships a valid activation
document, but never becomes user consent or implicit desired state. Planning
owns the whole document, allows no overlapping install, resource, or MCP
claim, and prepares a canonical `0600` replacement through the existing
journaled configuration boundary. Static TUI startup does not inspect these
exact targets. The final TUI screen sends the complete user request through
application review, which rebuilds a fresh observation scoped to selected
adapters whose `DEV` state was configured and previously managed adapters that
are being deselected. A selected adapter with an unconfigured diagnostics
section remains untouched. Startup targets and final review are pinned to the
same release identity for the session. The lifecycle derives the optional
install feature from the validated diagnostics choice rather than accepting a
second independent feature list. `DEV` prepares a complete schema-v1 document;
its feedback field controls the optional skill unit. Disabling `DEV`, removing
an adapter, or requesting complete uninstall prepares explicit removal of the
activation document and of any owned feedback unit. Preparation fails closed
when an in-scope adapter lacks exactly one matching activation resource. The
TUI retains the reviewed plan opaquely but still exposes no Apply capability.

The configuration boundary expresses removal through both a named `absent`
intent and a non-zero `remove_exact_document` mutation disposition. That
destructive disposition is valid only for `mainframe/diagnostics.json` under
the four adapter-owned roots. Removal moves only the exact observed activation
file into the private transaction workspace, supports rollback after an
interrupted rename, and never touches adapter-local databases, reports, or
other diagnostic history. Adapter deselection and complete uninstall derive
removal only from registry-backed managed installation state. Foreign,
unclaimed, selected-but-unconfigured, and host-incompatible adapters are not
changed.

The current `hub.html` is static, repo-oriented, and reads one legacy database.
It is not yet the finished local dashboard. A later
`mainframe diagnostics serve` command may reuse its visual and query layer
while serving adapter-owned stores on demand over loopback only. It must not
require an always-running system service; persistence through a per-user
service can be considered only after the on-demand path is complete and
measured.

## MCP onboarding is catalog-driven and adapter-owned

MAINFRAME may ship a verified catalog of MCP server descriptions and adapter
recipes, but an MCP connection is always an explicit user choice. The user
selects one connection profile and then independently selects the adapters
that should receive it. Each adapter owns and observes only its own projected
configuration; no adapter discovers an MCP server by reading another
adapter's configuration.

The TUI exposes MCP setup only after at least one environment is selected. With
no desired environment the overview keeps MCP and diagnostics unavailable and
explains why; the combined-plan entry remains available, so a complete
uninstall is still possible. The catalog is a list: opening one server reveals
its evidence, profiles, and compatible selected adapters. Returning saves only
a draft and goes back to the overview. Every screen states that the machine
remains unchanged until the complete plan is reviewed and confirmed;
individual MCP screens never apply partial changes.

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

Credential values never enter the release, project files, previews, logs, or
executor journal. The TUI accepts and previews only validated secret-reference
names. A keyed MCP profile selects a compatible user-owned credential instance;
it never collects an API key value. If an adapter cannot consume a reference
without leaking the value, that profile is unsupported for that adapter
instead of embedding the key in clear text.

Credential descriptions use a strict versioned contract with three owners:
MAINFRAME ships immutable service definitions, the user owns neutral instance
metadata, and a secret backend owns values. Catalog documents contain only
validated secret references. Several instances may use one service definition;
there is no implicit default when more than one matches.

A credential may name another credential needed to use, obtain, rotate, or
recover it. Relations are directed, advisory, and non-transitive. They never
authorize automatic retrieval or execution; duplicate, self, missing, and
cyclic relations are invalid. MCP-backed definitions reference the MCP catalog
instead of duplicating connection or evidence fields, and declare the expected
credential kind so a retained profile identifier cannot hide authentication
drift.

Parsing is read-only and fails closed on unknown versions, fields, malformed
or oversized documents, and invalid references without rewriting user data.
Structural validity does not claim that a secret exists. The current milestone
adds the machine-readable `mainframe credentials` command. It reads the
optional user document from
`credentials-config/mainframe/instances.json` through the no-follow,
identity-checked host reader. Missing state is an empty instance list; unsafe
or invalid state fails without partial output or reflected metadata.

The response is a dedicated versioned JSON contract, not a serialization of
internal structs. It explicitly reports `secret_availability` as `unchecked`
and exposes only definitions, instance metadata, and validated secret-reference
names. The command does not inspect referenced environment-variable values,
invoke `secret`, read `secrets.env`, migrate legacy indexes, write user state,
or resolve values. User state editing belongs to the terminal interface
described below.

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

The terminal interface now includes a neutral credential-service list that is
available independently of adapter selection. Creating or editing an instance
changes only an in-memory draft until the complete review shows the exact
metadata change. The user must then open a second confirmation screen. Apply is
enabled only when the executable plan contains the single
`credentials-config/mainframe/instances.json` mutation and no adapter, MCP, or
DEV mutation. The application revalidates the exact canonical after-image
before publication, then uses the common transaction for refreshed inspection,
atomic publication, rollback, and crash recovery. The TUI completes any
previously authorized unfinished transaction before it loads settings and
reports recovery warnings. Credential confirmation itself uses a
non-recovering executor path, so a new pending journal that appears after review
blocks the write instead of changing an unrelated target.

Existing state must be a regular strict-version document with mode `0600`;
missing state is created with mode `0600` and newly created parents use `0700`.
Malformed, unknown-version, symbolic-link, unsafe-mode, or concurrently changed
state fails closed without replacing user data. A keyed MCP profile selects a
matching credential instance and never accepts a raw key. Context7's keyless
remote profile is verified for Claude Code, Codex, OpenCode, and Antigravity
2.x. Its keyed remote profile is verified for Claude Code, Codex, and OpenCode;
Antigravity 2.x is explicitly unsupported until a plaintext-free secret
reference is proven. Optional GitHub stars are fetched asynchronously, kept
only in memory, and discarded when stale or unavailable.

The second read-only milestone gives keyless Context7 exact OpenCode, Claude
Code, Codex, and Antigravity 2.x projections. Bundle schema version 2 links each
projection to the catalog server and profile instead of repeating the endpoint
or authentication data. Bundle schema version 3 adds a strict
`host_requirements` collection without changing the release-index schema. A
release may contain both bundle versions, and the loader continues to accept
cached version 2 bundles. Antigravity is the first version 3 bundle: it records
`com.google.antigravity` version `2.2.1`, the exact native host covered by live
evidence. Every version 3 bundle must declare at least one requirement. All
requirement rows must hold, while any exact version listed within one row may
satisfy that row. The launcher inspects bounded `Info.plist` files under the
system and user application directories, supports both XML and binary property
lists, and exposes only bundle identifiers and versions to the lifecycle. A
complete scan distinguishes a missing application from an installed unsupported
version; an incomplete or unavailable scan fails closed for that adapter. The
scan has shared entry, byte, and retained-result limits across both application
directories. Unsafe or oversized metadata is never rendered. Multiple detected
copies are accepted only when every copy uses a supported exact version; a
supported and unsupported pair is reported as incompatible rather than guessing
which copy the operating system will launch.

The TUI enforces the requirement only for Antigravity. A compatible application
makes the adapter selectable. A missing, unsupported, or safely unverifiable
application removes only Antigravity from the choices and explains the fixed
reason without exposing paths or parser errors. If an incompatible Antigravity
adapter is already installed, filesystem and configuration planners preserve
its complete dependency closure without repair or removal. Explicit selection
is rejected again by the lifecycle boundary. Claude Code, Codex, and OpenCode
remain usable. The legacy `install.sh` path continues to accept Antigravity 2.x
while the TUI uses the narrower evidence-backed managed policy.

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
non-finite TOML values as equivalent JSON ownership state. On the exact
supported standalone Antigravity 2.2.1 host, MAINFRAME owns only
`mcpServers.context7` in `~/.gemini/config/mcp_config.json` and emits the
adapter-native `serverUrl` field. Its ownership registry remains under
Antigravity's separate data root, not in another adapter or the
runtime-consumed MCP file. Live probes establish only that this host executes a
synthetic command from that path instead of a standalone file at the observed
alternative path.

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
[OpenCode MCP contract](https://opencode.ai/docs/mcp-servers/), the official
[Antigravity 2.0 product boundary](https://antigravity.google/docs/overview?hl=en),
the product-specific [Antigravity MCP guidance](https://antigravity.google/docs/mcp),
and live probes of the exact supported standalone Antigravity 2.2.1 host.

Before execution, the immutable inspection can materialize a private prepared
plan without writing. It preserves complete user JSON, composes non-overlapping
resources sharing one physical file, and groups each configuration with its
ownership registry. Every file mutation is bound to exact captured bytes, mode,
and a strengthened identity fingerprint containing device, inode, and birth
timestamp; missing files use an explicit absence precondition.
Prepared bytes remain outside the executor journal. Any unresolved issue,
unsupported changed strategy, incomplete snapshot, or target collision fails
the whole preparation with no partial result.

Claude Code Context7 preparation owns only the exact user-scope
`~/.claude.json` `mcpServers.<server>` entry and its separate registry under
`~/.claude/mainframe/`. The ordered-JSON materializer preserves unrelated
preferences, projects, and sibling MCP entries while using Claude's explicit
`type: http` dialect. Missing files are private, existing files are rebound to
their captured identity, and relinquishment changes only the registry. The
home root remains available only through the exact release-validated
`.claude.json` projection; it does not become a general Claude Code target.

Antigravity Context7 preparation owns only the exact
`~/.gemini/config/mcp_config.json` `mcpServers.<server>` entry and the registry
under `~/.gemini/antigravity/mainframe/`. The ordered-JSON materializer
preserves unrelated servers and unknown top-level fields while emitting only
the `serverUrl` dialect selected by MAINFRAME. It never writes
`~/.gemini/antigravity/mcp_config.json`. A direct symbolic link from that path
to the independently inspected canonical regular file represents the same
configuration and requires no migration. Its identity and exact target become a
read-only transaction precondition, so replacement after preview aborts before
any write. Any standalone file or other link at the noncanonical path requires
explicit resolution before Antigravity MCP Apply. These raw-path semantics are
an observed compatibility contract based on synthetic-command probes of the
exact supported standalone Antigravity 2.2.1 host, not a behavior inferred from
Antigravity IDE documentation. The probes do not establish ownership scope or
configuration dialect. “Canonical”, “noncanonical”, and “legacy” are MAINFRAME
classification terms, not vendor labels for these paths.

OpenCode Context7 preparation uses the same ordered-JSON boundary as its
permission ownership without sharing ownership between them. When both change
`opencode.json`, MCP preparation starts from the permission plan's after-image
only after their complete before-images match, then updates only
`mcp.<server>`. Release validation independently proves that their JSON
pointers do not overlap. The result is one recoverable transition containing
the shared configuration and both adapter-local registries. Multiple OpenCode
MCP entries sharing that target and registry are applied deterministically;
registry-only relinquishment remains a separate transition. No CLI or TUI
Apply path is introduced by this preparation boundary.

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

Direct developer-mode bundle builders use the same isolation boundary without
rewriting their active output file by file. Each builder materializes and
validates a complete private sibling tree, then publishes it with one
platform-native no-replace or exchange rename under a persistent lock. A small
identity-bound journal makes interruption before or after that rename
recoverable and never enters a complete release payload. The direct parent and
managed output entry are opened without following symbolic links; the rest of
the caller-supplied parent chain remains an explicit trust boundary. The
previous generation is retained until the next successful publication instead
of being deleted during the exchange. A lookup that begins at the public output
name therefore resolves through a complete old or new tree, while a runtime
that pins an older directory across multiple publications can outlive that one
retained generation. Separate reads spanning the commit may also cross
generations. This is cooperative process recovery, not a same-user security
boundary or a full Darwin power-loss guarantee.

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

Automatic link ownership comes only from the durable registry at
`${XDG_STATE_HOME:-$HOME/.local/state}/mainframe/link-ownership.json`. Each
claim binds one stable release unit ID and component to one logical target,
the exact raw symbolic-link target, and the release ID plus index digest that
created it. Device, inode, and birth timestamp are deliberately not persisted
there; discovery captures the complete live link identity for every preview,
and Apply checks that fresh identity again before changing a public name. A
claim whose link was removed can be repaired or relinquished without requiring
the old release payload. A user-changed link or non-link entry is never removed:
MAINFRAME drops only its claim and leaves the user entry untouched.

An exact link created earlier by `install.sh` has no registry claim. When it
points to a live artifact in the currently validated release, the plan exposes
a separate adoption operation. Adoption changes only the registry, after
rechecking the link target and inode immediately before and after claim
publication; a mismatch rolls the claim back. It does not replace the public link.
Matching an older path suffix is not enough for adoption. This one-time bridge
keeps existing installations usable without treating arbitrary historical or
user-created links as managed.

Updating a claimed link uses one platform-native atomic exchange: macOS
`RENAME_SWAP` or Linux `RENAME_EXCHANGE`. The new staged link becomes public
while the exact previous inode moves into the private workspace in the same
namespace operation. The ownership transition is recorded in the same
recoverable transaction. A failure before either durable boundary restores
both the previous link and its previous claim; committed cleanup removes only
the verified retained inode.

Every parent and private directory is opened descriptor-relatively without
following symbolic links and checked against its recorded identity. Detected
concurrent changes before a namespace transition fail closed. The operating
systems do not atomically bind a no-replace rename's source name to a previously
observed inode. Another same-user writer that does not share MAINFRAME's
transaction lock can therefore replace the source in that narrow interval; the
replacement inode is retained rather than unlinked, but its public name may be
moved.

Configuration changes participate in the same lock and transaction as link and
directory changes. Journal schema version 4 records explicit present or absent
configuration after-images using only targets, content digests, modes, file
identity fingerprints, and private names; configuration bytes remain in
the immutable prepared plan held by the process. Every persisted fingerprint
combines device, inode, and birth timestamp. Darwin support is limited to local
APFS and HFS filesystems and reads their native birth timestamp from `stat`;
Linux requires `statx` to return `STATX_BTIME`. Apply fails closed when the
supported filesystem cannot provide that signal.

The birth timestamp materially reduces the inode-reuse window but is not a
filesystem generation number. A filesystem may expose it at coarse resolution,
so a same-inode recreation inside one timestamp quantum remains a residual
collision risk. The executor must not describe this fingerprint as an absolute
ABA-prevention guarantee; a future generation or file-handle signal is still
needed where the platform can provide one safely.

Only empty prior journals can be upgraded automatically to schema version 4.
An identity-bearing version 2 or 3 journal cannot recover a birth timestamp
after the fact, so it fails closed and instructs the operator to recover it
with a binary that understands its original schema. A version 2 journal also
cannot claim an absent after-image because that state did not exist in its
contract.

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
Removing an exact configuration uses an explicit absent after-image and
atomically moves the verified public before-image into that same private
directory; it does not stage an empty replacement file. A crash before the
rename leaves the public file in place, while a crash after the rename is
recognized from the retained before-image and rolled back from the journal.
If another same-user process substitutes the source during the rename window,
the mismatched file is moved back to the still-empty public name before the
transaction fails.
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
