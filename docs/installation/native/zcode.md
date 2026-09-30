# ZCode Desktop adaptation

Reviewed 2026-09-08 against official documentation and the installed macOS
application, version 3.11.2 (build 3.11.2.6792), with a bounded skill-update
compatibility review on 2026-09-22 for 3.14.3.7762. Use the [maintained installer](../zcode-installer.md) for delivery. This page
records mapping evidence and the boundaries still requiring native acceptance. Target Desktop; the configuration directory's `cli` name does
not require launching a CLI agent.

## Native destinations

| Inventory category | Global destination and adaptation |
| --- | --- |
| Global instruction | Merge canonical `instructions/global.md` into `~/.zcode/AGENTS.md`, preserving user instructions and resolving actual conflicts |
| Skills | `~/.zcode/skills/<name>/SKILL.md`, including every required relative resource; resolve MAINFRAME root and credential-index placeholders in target copies |
| Agents | `~/.zcode/agents/<name>.md`; translate role metadata and required-method links to native skills |
| Commands | `~/.zcode/commands/<name>.md`; keep explicit workflows as native slash commands |
| Hooks | User configuration `~/.zcode/cli/config.json`, under `hooks.events`; preserve unrelated keys and registrations |
| Credentials | Follow the shared [credential component](../components/credentials.md); reuse a compatible helper and the canonical non-secret index |

The application's bundled `zcode-configuration-guide` and diagnostic skills
confirm these roots and precedence. Read the corresponding bundled guide only
for an unresolved schema detail; do not load the whole guide plugin. Its table
allows workspace hooks, but the current official hook page says workspace hooks
are ignored. Use the documented global route and keep the discrepancy explicit;
neither source proves live dispatch in this installed build.

## Skills and explicit commands

Keep skill `name` and `description` as native top-level frontmatter. Put the
concrete trigger and benefit early: ZCode presents only an initial description
excerpt to the model. Keep supporting material behind relevant links instead of
expanding the entrypoint. The documented description limit is 1,024 characters.
[Skill documentation](https://zcode.z.ai/en/docs/skill)

Native commands use the filename as their identity and accept `description` and
`argument-hint` metadata. Preserve each canonical command's invocation boundary
and body; do not introduce model/tool overrides without a specific need.
[Command documentation](https://zcode.z.ai/en/docs/commands)

Scheduled-task instructions are sent directly to the Agent and do not pass
through the interactive input box that expands native slash commands. The
read-only `mainframe-tickets-find` workflow therefore also has a narrow skill
projection with the same name. It loads only when the user or automation text
explicitly requests `/mainframe-tickets-find` or `$mainframe-tickets-find`.
Keep the native command for interactive use. Do not mirror the mutating or
session-ownership commands into automatically selectable skills without a
separate demonstrated noninteractive need.

After creating or changing any ZCode skill file, keep one **Settings -> Skills
-> Refresh** handoff followed by a new Desktop session. A converged filesystem
does not prove that the running app refreshed its skill catalog.

Invoke a native command by itself, for example `/mainframe-project-skill`. ZCode treats
everything after the built-in `/goal` as goal text, so `/goal /mainframe-project-skill`
sets or replaces a goal instead of invoking `mainframe-project-skill`; slash commands do
not nest. The `$name` form selects a skill and is a different native mechanism.
If diagnosis finds `~/.agents/skills/mainframe-project-skill`, first inspect the actual
native command at `~/.zcode/commands/mainframe-project-skill.md`. An empty shared
directory is migration residue, not a missing skill that should be recreated.

ZCode also discovers `~/.agents/skills`. An older coexisting MAINFRAME Codex installation can put
command-shaped skills there. The current maintained Codex adapter uses its
private skill root; see [migration](../codex-installer.md#migration-from-the-shared-skill-root). Its `agents/openai.yaml` does not establish ZCode's
explicit-only behavior. Before adding a native command, inspect only matching
inventory identities for this collision. The bundled `diagnosing-skills` guide
documents disabling an individual skill by absolute path with `enable: false`.
Use ZCode's supported setting after verifying its actual container schema; do
not guess JSON, disable all skills, delete Codex files, or edit their shared
bodies. Keep a command pending until its native invocation exists without an
automatically selectable duplicate.

## Roles

Use native `name` and `description`. The documented model field supports a
specific available model or `inherit`; `thoughtLevel` applies with a specific
model. `reasoningEffort` is not the native field. Select an available model and
level only when the role and task justify them. Preserve the MAINFRAME required
skill as an actual method, not merely a role label. If narrowing tools, verify
the exact skill-invocation tool remains available. Native agent definitions need
a new session; do not repeatedly poll for hot reload.

ZCode Settings rewrites agent files when the user selects a model, thought
level, color, or AGENTS.md injection policy. Treat those four supported fields
as per-installation native settings: preserve compatible edits and reconcile
their exact bytes into the ownership receipt. Continue to reject edits to the
role body, description, name, or tool boundary. New installations inherit the
current session defaults unless the user configures a role; do not hard-pin one
account's provider model in canonical source.
[Subagent documentation](https://zcode.z.ai/en/docs/subagents)

## Hook transport and acceptance gates

Use the existing canonical detectors; a ZCode binding must normalize native
input/output without changing detector semantics. Configuration-file hooks need
`hooks.enabled: true`. Prefer a bounded synchronous `process` registration with
separate `command` and `args`; native `timeoutMs` is milliseconds. Sessions capture
hook configuration, so a change requires a new session. A disabled registration
must not invoke a missing executable.
[Hook documentation](https://zcode.z.ai/en/docs/hooks)

ZCode runs hooks from one source in array order. Register the four Bash
pre-action detectors through one product-private `mainframe-pre-shell` bridge
process so the same payload starts Python once. The bridge runs the canonical
detectors in inventory order, preserves their individual disable markers,
deduplicates advice, and aggregates output with denial taking precedence.
SessionStart root capture and the Write/Edit/Stop quality lifecycle remain
separate registrations because they consume different events and state.

| MAINFRAME hook | Mapping and proof required before activation |
| --- | --- |
| `mainframe-secret-access` | `PreToolUse` shell input to canonical command; positively recognized denial to native `permissionDecision: deny`; ordinary commands retain native permission handling |
| `mainframe-rg-short-replace` | `PreToolUse` command plus `additionalContext`; prove the advice arrives and execution is not denied |
| `mainframe-destructive-operations` | Capture runtime workspace root at native `SessionStart` startup/clear/compact/resume; combine with actual pre-Bash cwd. Missing capture is neutral. |
| `mainframe-commit-secrets` | Native pre-Bash cwd is the execution cwd; pass it to canonical staged-content inspection. |
| `mainframe-code-quality` | Retain `PreToolUse` capture and matching `PostToolUse` or `PostToolUseFailure` attribution for native `Write|Edit`; use `Stop` only for a positive revalidating block. The full contract remains unsupported because advisory-only Stop output is discarded unless it requests another model turn. |
| `mainframe-fallow-quality` | Unsupported completion advisory: Stop advice is discarded unless it requests another model turn. Do not convert an advisory into forced continuation. |

This is the smallest event set that preserves the canonical timing and effect:

- `PreToolUse` is required for the four shell rules and the edit baseline.
  `PermissionRequest` runs only when ZCode would ask the user, so it would miss
  automatically admitted calls; post events are too late for a guard.
- `PostToolUse` reports a successful edit while the responsible model can still
  act. `PostToolUseFailure` only retires the matching baseline so a failed edit
  cannot leave stale attribution.
- `Stop` is used only to revalidate and block a still-live attributed quality
  finding. ZCode ignores matchers for Stop and caps continuation at three, so
  the clean path must remain silent. Completion-only advisories are left
  unsupported instead of forcing another model turn.
- `SessionStart` is the only event that supplies the initialized runtime root
  before later Bash calls can change cwd. The current bundle emits startup and
  resume; clear and compact remain accepted because they are documented native
  sources and cost nothing unless emitted.

`UserPromptSubmit` has no exact tool input and is not a substitute for any of
these bindings. Do not add a hook there merely to remind the model of policy.

The official hook page documents snake_case event fields and camelCase aliases,
JSON denial/context output, and empty successful output. This establishes a
candidate transport, not successful delivery of any MAINFRAME hook. Before
activation, use harmless fixtures for relevant command fields, neutral output,
denial, advisory, and disable/re-enable behavior. Retire callbacks before moving
executables and keep any cached entrypoint inert after disable. Never consume
transcripts to reconstruct missing operation context.

## Bounded installation and separate acceptance

Follow [zcode-installer.md](../zcode-installer.md), which owns the finite
plan/apply/verify route and recognized manual-installation adoption. Do not
regenerate wrappers or replay the probes above during ordinary installation.
Those probes describe separately assigned adapter validation.

The maintained mapping delivers four pre-shell hooks and retains the supported
`mainframe-code-quality` edit and blocking lifecycle for the primary runtime. The two
complete completion contracts remain unsupported in this inspected build;
`mainframe-code-quality` carries the exact partial-binding limitation. Default subagent
runtimes omit hook runners, so primary protection must not be generalized to
delegated tool calls. See the
[reproducible native code evidence](zcode-evidence.md) for exact functions,
source fingerprint, extracted-function experiments, and live acceptance. The
four pre-shell effects and the primary-runtime `mainframe-code-quality` post-edit and
positive Stop lifecycle have live Desktop evidence on this build. The
advisory-only Stop limitation, default-subagent omission, and cached-callback
retirement boundary remain unproven or unsupported as stated above.
