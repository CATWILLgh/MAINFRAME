# Codex orientation

Last reviewed: 2026-10-02.

Use the [maintained Codex installer](../codex-installer.md) for its inspected
runtime mapping. This page owns native evidence and revalidation decisions;
the installer owns repeatable packaging and lifecycle operations. Recheck the
version, effective home/configuration layers, and requested Desktop/CLI surface.
Revisit the relevant official contract when a mapping or observed behavior
changes instead of repeating full adaptation research for an unchanged runtime.

## Desktop 0.159.2 delivery revalidation

The current Desktop task reported engine `0.159.2`. Compare the exact upstream
tags [0.153.4](https://github.com/openai/codex/tree/rust-v0.153.4) and
[0.159.2](https://github.com/openai/codex/tree/rust-v0.159.2), not a latest branch.
The non-truncated Git trees resolve to `3d2ee51ca2d5db578f328aa75e20aa22c0197c9a`
and `ff6aec96948b70d94983af2641a6b67c94faeff5`. Downloaded relevant files were
checked against their Git blob hashes.

- Native config definitions used by MAINFRAME (`AgentsToml`, `SkillsConfig`,
  `HooksToml`, `HookHandlerConfig`, `SandboxWorkspaceWrite`, `SandboxMode`,
  `PermissionsToml`) are unchanged in the tagged
  [config schema](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/core/config.schema.json).
  The [custom-role configuration](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/agent-roles/src/agent_role_config.rs)
  is also unchanged. This preserves packaging, not proof of parent permission
  enforcement for read-only roles.
- [Host skill roots](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/ext/skills/src/host_roots.rs),
  metadata parsing and host merge rules are unchanged. `$CODEX_HOME/skills`
  remains a supported compatibility root. Host discovery now passes an
  unrestricted filesystem accessor; it preserves that root's previous access
  semantics. Cloud-provider renaming does not change local skill packaging.
- [Global instructions](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/codex-home/src/instructions/mod.rs)
  still prefer `AGENTS.override.md` then `AGENTS.md`. The newer reader retains
  its last good value on read failures and deduplicates warnings. Confirmed
  absence still clears the cache; a failed read does not prove an update loaded.
- `PreToolUse`, `PostToolUse`, and `Stop` event implementations and generated
  input/output schemas, hook configuration, and tool-name mapping have identical
  Git blob hashes. The actual-tool-workdir, exact attributed diff, and
  non-blocking completion-context limitations remain. Preserve useful partial
  bindings and do not claim those missing guarantees became supported.
- The [runtime dispatcher](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/core/src/hook_runtime.rs)
  now supplies the local environment's `cwd` for pre/post tool events, falling
  back to the turn directory. This still does not identify a shell call's own
  working directory. `Stop` retains the turn directory. Forked subagents now
  receive start events; MAINFRAME does not bind that event.
- The [command runner](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/hooks/src/engine/command_runner.rs)
  drains output while writing input and includes both in the timeout. Unix
  handlers launch in a new process session; restricted environment names are
  filtered from both the session snapshot and hook overrides. No MAINFRAME
  transport change follows from these inspected differences.

The maintained adapter permits this exact Desktop version; unknown versions and
CLI 0.159.2 remain outside this revalidation. Disposable-home checks cover full
skill resource delivery, state truthfulness, convergence, preservation and
rejection before writes for an uninspected surface/version. Native discovery,
trust, lifecycle execution and read-only role behavior remain separate pending
acceptance. A fresh task is the shared loading handoff after delivery changes.

## Official sources

- [AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Skills](https://learn.chatgpt.com/docs/build-skills)
- [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Hooks](https://learn.chatgpt.com/docs/hooks)
- [Custom prompts](https://learn.chatgpt.com/docs/custom-prompts)
- [App-server](https://learn.chatgpt.com/docs/app-server)

## Current orientation

| MAINFRAME concern | Native direction to verify |
| --- | --- |
| Global instruction | Codex's global `AGENTS.md` or override layer, preserving user-owned content and precedence |
| Skills | Use the verified private `$CODEX_HOME/skills` mapping below; preserve bundled `.system` skills |
| Agents | Custom agent configuration with per-role instructions, model defaults, sandbox, tools, and skill attachment where supported |
| Commands | Explicit user invocation is required; current custom prompts are documented as deprecated, so first determine whether a user-only skill or another current native command surface preserves the command contract |
| Hooks | `hooks.json` or inline hook configuration at an effective native config layer, with a thin wrapper around canonical detectors |
| Settings and permissions | Effective Codex configuration and sandbox/approval layers, preserving managed and user precedence |

Codex currently documents matching hooks as concurrent. Do not use registration
order as a safety dependency. Each MAINFRAME wrapper must be independently
correct, bounded, and safe when several hooks, sessions, or subagents run at
once.

For the inspected 0.153.4 Desktop engine, all four pre-shell identities share
one `PreToolUse` `^Bash$` command transport. The bridge still dispatches and
disables each canonical identity independently, but starts one Python process
and emits one bounded native result. A denial wins while any distinct advisory
is retained. A clean event emits no stdout or stderr and adds no model context.

## Adaptation decisions

1. Identify the current surface's runtime version, configuration home, skill
   catalog, agent registry, and hook dispatcher. Compare Desktop and CLI only
   when the user explicitly requested both, under the
   [surface rule](../verification.md#desktop-and-cli).
2. Resolve the effective global instruction chain before merging the
   MAINFRAME-owned section. Root [AGENTS.md](../../../AGENTS.md) in this
   repository remains project guidance, not the global payload source.
3. Use the maintained private skill destination below and prove catalog
   visibility and body loading when revalidating a runtime.
4. Generate native custom-agent files or configuration from each role matrix.
   Preserve task-specific model selection under the
   [agent guide](../components/agents.md), including explicit user choices.
5. For commands, prefer a current mechanism that keeps content out of routine
   context and is only user-invocable. Record a degradation if Codex cannot
   represent both properties.
6. Bind hooks only to documented events whose timing and output contract match
   the canonical rule. Verify subagent delivery separately where relevant.

## Decisions that require separate proof

### Explicit commands

The [skills documentation](https://learn.chatgpt.com/docs/build-skills) provides
`policy.allow_implicit_invocation: false` in an installed skill's
`agents/openai.yaml`; explicit `$skill-name` invocation remains available. Check
this route before declaring a command unsupported. Keep the canonical command
body unchanged apart from documented adaptation, and report any remaining
catalog exposure or change from slash syntax as a degradation.

The [deprecated prompt mechanism](https://learn.chatgpt.com/docs/custom-prompts)
is documented for CLI and IDE extension. An interactive CLI rejecting
`/prompts:name` establishes a failure on that CLI version only. It neither
disproves the explicit skill route nor tests Desktop. Passing slash text to a
non-interactive model prompt also does not test the interactive command parser.

### Agent identity and restrictions

The [custom-agent contract](https://learn.chatgpt.com/docs/agent-configuration/subagents)
uses each TOML file's `name` as its identity and requires `description` and
`developer_instructions`. Parsing these fields proves structure only. Check the
effective catalog for every MAINFRAME identity, then perform the role probes
in the [agent guide](../components/agents.md).

Codex documents that live parent sandbox and approval overrides are reapplied
when spawning children. A role file containing `sandbox_mode = "read-only"`
therefore does not prove read-only enforcement under the active parent mode.
Test the effective restriction without changing the user's permission posture;
record an enforcement gap instead of claiming the file guarantees isolation.

Codex documents that explicit `model` and `model_reasoning_effort` fields in a
custom-agent file override spawn choices. When those fields are absent, native
spawn values precede `[agents]` defaults and parent settings. Avoid unnecessary
role-file pins; verify the actual child's model and effort, including their
compatibility, through the installed interface. Recheck its current schema and
any context-inheritance restrictions before claiming per-task selection works.

In the 2026-09-07 installation probe on runtime 0.153.4, a custom-role spawn
from `exec --ephemeral` failed with a missing parent-thread error. The same role
loaded from a disposable persisted parent. If this recurs, use that supported
parent lifecycle only for the role check, record its exact identity, and clean
up only probe-owned tasks. The first failure does not establish an unsupported
role, and successful loading does not establish its permissions.

### Hook input and output

The [hook reference](https://learn.chatgpt.com/docs/hooks) currently describes
`tool_input.command` for both shell and patch tools. Verify the actual shape
for each tool in each installed runtime before writing normalization. A wrapper
tested only with a hand-authored payload can agree with its own wrong field
assumption. Use an actual harmless edit to prove pre/post operation pairing,
finding delivery, completion continuation, and resolution. Retain only the
minimal sanitized fixture needed for the adapter check, never a transcript or
raw sensitive payload.

The 2026-09-07 probes on CLI 0.153.4 and the Desktop-bundled 0.153.4 executable
established these narrower facts; they do not prove live Desktop UI dispatch:

| Observation | Consequence for adaptation |
| --- | --- |
| A shell tool ran in an explicit working directory different from the session directory; its hook input contained the command and session `cwd`, but no actual tool workdir | Do not substitute session `cwd` for the directory-dependent destructive or commit guard inputs |
| A denied patch emitted a pre event without a failed post event; an allowed patch emitted the matching successful pair | Use the catalog's unmatched-snapshot expiry path; test successful edit attribution, completion blocking, repair, and release separately |
| The documented completion output offered blocking continuation or a UI message, with no documented non-blocking model context | Do not treat a UI message as Fallow's model advisory or as proof of the mainframe-code-quality unavailable-check channel |
| A probe override passed through `thread/start.config` did not activate its fixture; process-level configuration did | Confirm the exact probe registration and actual callback delivery before interpreting silence; recheck current configuration APIs instead of copying an old injection attempt |

The first observation is a demonstrated input gap for those runtimes; the
completion-channel limitation follows the current official contract. Recheck
each after a relevant runtime change. A missing failed post alone is not proof
that `mainframe-code-quality` cannot be adapted, and its supported expiry does not settle
the separate completion advisory requirement.

The maintained adapter therefore retains the supported core instead of dropping
the whole component. `PreToolUse` on `apply_patch` captures the explicit patch
paths, matching `PostToolUse` reports newly introduced findings, and `Stop`
revalidates and blocks only unresolved attributed findings. A true native
`stop_hook_active` makes a repeated callback silent, so one unresolved finding
can create at most one automatic continuation in a turn; its state remains for
revalidation on the next user turn. Completion-only
unavailable-check advice stays silent because forcing another model turn would
change its non-blocking contract. This partial binding remains explicit in the
installation report and does not make the full component supported.

The two shell guards whose full contracts need the Bash tool's actual working
directory also retain the strongest safe subset. Codex supplies the exact
command to `PreToolUse`, but its common `cwd` is the session directory and can
differ from the Bash tool's execution directory. The adapter therefore keeps
only decisions independent of that missing field:

- `mainframe-destructive-operations` blocks its narrow destructive Git forms,
  recursive deletion of `/` or the current user's home, and a relative
  recursive deletion after an in-command directory change;
- `mainframe-commit-secrets` blocks high-confidence secrets in literal commit
  metadata and absolute commit-message files.

Active-project-root deletion, ordinary relative deletion targets, staged or
worktree commit content, and relative commit-message files remain unsupported.
Using the session `cwd` for those decisions would create false blocks.
`PermissionRequest` is not an equivalent alternative because it fires only
when Codex already intends to ask for approval; `PostToolUse` cannot prevent a
side effect.

`mainframe-fallow-quality` remains wholly unbound after the same fallback
audit. Its contract requires an exact attributed in-memory diff. The available
Codex events cannot provide that diff after the edit without persisting source
content or reconstructing it from a dirty worktree that may include unrelated
user changes. A `Stop` placement would also force another model turn for an
advisory. Those placements are misleading or noisier than their decision
value, so omission is intentional rather than inferred from a missing preferred
event.

Do not guess patch input from a shell-tool example, infer subagent delivery from
a primary-session event, or label a missing snapshot as a clean result. Use the
[hook guide](../components/hooks.md) for the shared lifecycle and cleanup rules.

Live Desktop checks on 2026-09-08, engine 0.153.4, confirmed activation in an
existing primary task immediately after the user granted trust, without an app
restart. `mainframe-secret-access` denied harmless fake `mainframe-secret get` and value-bearing
`mainframe-secret set` actions before execution; an allowed fake action ran. The
`mainframe-rg-short-replace` advisory reached the model while the command succeeded, and
explicit `--replace` remained silent. Disabling the hooks silenced the live
ripgrep advisory and both cached callbacks, including synthetic Stop input.
Re-enabling restored both native findings with unchanged registrations and
ownership receipt. These checks establish current-task activation and bounded
disable/enable behavior; fresh-task and subagent delivery, and live uninstall,
still require separate evidence.

The restored `mainframe-code-quality` binding was added after that live pass. Its detector
and transport lifecycle have deterministic fixture coverage, while current
Desktop discovery, trust, and behavior remain pending until a fresh-task check.

### Hook disable and removal

The [hook reference](https://learn.chatgpt.com/docs/hooks) documents `/hooks` in
CLI for disabling individual non-managed hooks. Verify the available control
and its effect on the actual Desktop or CLI runtime; deleting `hooks.json` is
not evidence that running callbacks unloaded.

During the 2026-09-07 Desktop reset, removing the registered adapter file after
its on-disk registration caused cached `PreToolUse` calls to block tools and
cached `Stop` calls to continue the task repeatedly. Python's missing-script
exit code was `2`, which Codex also uses for hook denial or continuation.
This is an observed failure, not a documented guarantee about reload timing.

Guard the launch boundary and distinguish process failure from an actual
finding. Verify a native neutral result on both pre-tool and completion events;
do not pass through raw interpreter exit codes or use a permission-allow result
to suppress failure. Follow the
[retirement sequence](../problems/rollback-and-recovery.md#retire-hooks-safely)
before removing files; retain the disabled entrypoint while reload is pending.

The maintained installer retains that entrypoint in the native command itself:
`/bin/sh` executes an inline disabled-marker and implementation-existence guard,
then suppresses raw interpreter failures. Removing owned implementation files
therefore leaves a callable neutral command. Isolated shell tests cover missing
implementation, exit `2`, disable, and uninstall with cached commands; they do
not prove live Desktop unloading. Older file-only launchers still require the
general retirement sequence.

## Useful probes

On 2026-09-08 the current Desktop task exposed `CODEX_THREAD_ID`; an exact
read-only lookup of that ID in `state_5.sqlite`, column `threads.cli_version`,
returned engine 0.153.4. The installer uses only this one metadata field for
Desktop version selection. It never reads a rollout, scans other task rows, or
uses the app release number as the engine version. Missing metadata requires
explicit current app evidence; it does not trigger CLI discovery.

These are adapter validation recipes, not an ordinary installation checklist.
Stay within the [requested surface](../verification.md#desktop-and-cli).

For CLI zero-model discovery, `skills/list` and `hooks/list` on the inspected 0.153.4
app-server both take **`cwds`**, an array. Its generated schema and a read-only
round trip on 2026-09-07 confirmed both returned the requested temporary scope.
Passing `cwd` to `hooks/list` does not establish that scope. The maintained
client checks the response scope, exact identities, native hook source, trust,
and enabled state. Catalog success alone does not prove body loading, child
permissions, event delivery, or Desktop reload.

- Identify the current surface's engine version without changing it. In Desktop,
  use app runtime metadata; do not invoke the CLI to obtain a substitute version.
- Use the native skills surface or listing, then invoke one harmless installed
  skill and confirm a referenced file loads.
- Start a fresh session to prove instruction changes.
- List or invoke one custom agent in an isolated scope and test its permission
  boundary.
- Trigger each hook with a harmless synthetic action on the requested surface;
  test both surfaces only when both were explicitly requested.

Do not report the desktop app as verified because the CLI parsed the same file.
Do not install deprecated prompt copies alongside a working current command
representation merely for compatibility.

## Private user skill destination

On 2026-09-08, the current Desktop task's newly created native child session
received an ordinary probe skill from `/Users/user/.codex/skills` in its supplied
catalog. It read the skill and its linked resource successfully without being
given the path or marker. This proves discovery and resource loading in that
native child; primary-session refresh and explicit-command UI selection remain
separate boundaries. No CLI process or standalone app-server was launched.

On 2026-09-11, a fresh primary Desktop task on the same engine exposed all 14
MAINFRAME private-root skills and all six then-current custom roles in its native catalog.
The current official skill page still lists `$HOME/.agents/skills`, not the
private Codex root, while documenting `allow_implicit_invocation: false` and
explicit `$skill` invocation. Keep the private destination grounded in observed
runtime behavior and revalidate it when the engine changes.

The maintained 0.153.4 mapping now places MAINFRAME skills and command-shaped
skills under `$CODEX_HOME/skills`, keeping Codex-specific invocation metadata out
of the shared `$HOME/.agents/skills` root that ZCode also reads. The current
public skill guide lists the shared user root; this private-root choice relies
on the observed runtime evidence above, not on a claim that the documentation
lists it. Recheck it when changing the supported runtime.

Receipt reconciliation migrates only unchanged installer-owned shared copies,
updates role method links, and preserves unowned or edited files. It never
moves bundled `.system` skills. A preserved foreign shared copy may still need
an explicit cross-product collision decision; do not delete it to hide a
remaining duplicate.

## Prerelease content updates

On 2026-09-15 the current Desktop task's `threads.cli_version` reported
`0.154.0-alpha.6.2`. Its active catalog exposed the existing 14 ordinary
MAINFRAME skills from the private root and six then-current custom roles. This is evidence
for the existing text-loading format, not new hook dispatch or permission proof.
The former stable-version-only parser incorrectly reported this metadata as
missing; the parser now preserves prerelease identity and rejects a conflicting
explicit version instead of falling back to a different engine.

The maintained installer permits only an existing same-source bounded update
invoked from Desktop on this exact version. On 2026-09-15 Desktop reported that
`additionalContextLimit` was ignored on the installer-owned `Stop` hook because
that event cannot emit additional context. The [native Hooks documentation](https://learn.chatgpt.com/docs/hooks) confirms
that unsupported event/field combination is ignored with a configuration warning;
`Stop` instead uses its blocking decision and reason output. The generator now
omits the field from `Stop` while retaining it on `PreToolUse` and `PostToolUse`.
The prerelease validator allows exactly that removal from the receipt-owned
registration.

Prior installation surface is not an authorization input: other native bindings
must remain byte-identical, and current runtime/surface changes reset native
verification independently. Its validator rejects new/removal/mode changes,
executable resources, other native registration or permission changes, skill identity
or invocation metadata changes, and role fields other than description and body.
The normal receipt, concurrent-write, and transaction checks still apply.
Fixture tests cover successful update/convergence with protected native files
unchanged, refusal of fresh installs and altered boundaries, and preservation
of unknown hook compatibility as pending. No CLI or app-server is launched.

Full 0.154.0-alpha.6.2 installation and native hook acceptance remain unverified.
Do not generalize this bounded-update support to another runtime or use it
to introduce bindings. The [procedure](../codex-installer.md) reports the mode and
retains a fresh-task handoff for updated text.

## Commit checkpoint advisory

`mainframe-commit-checkpoint` uses PostToolUse (apply_patch) to deliver bounded
model context after successful edits. It is independently disableable and never
registers checkpoint advice at Stop or forces continuation. Defaults, metadata
bounds, reset/deduplication, failure behavior and coverage are owned by the
[canonical checkpoint contract](../../../hooks/README.md#adapt-mainframe-commit-checkpoint).
The maintained installer includes its detector and post-edit binding; native
activation remains a separate observation after installation.

## Skill reminder and Desktop 0.159.0-alpha.12.1

On 2026-10-03 the current parent and native child task metadata and bundled
`codex-package.json` identified **0.159.0-alpha.12.1**. The installed executable's
embedded `post-tool-use.command.input` schema includes optional `agent_id` and
`agent_type`; an in-place, keys-only temporary probe observed root and child
`Bash` callbacks with string output and `tool_input.command` only. No actual
shell working directory is supplied. These findings validate the reminder's
native payload/output route; they do not establish discovery or behavior of all
other installed components. Disposable-home packaging checks cover delivery.

[Hooks](https://learn.chatgpt.com/docs/hooks) documents nonblocking
`PostToolUse.additionalContext`. Nearby public source
[`rust-v0.159.0-alpha.12` hook runtime](https://github.com/openai/codex/blob/rust-v0.159.0-alpha.12/codex-rs/core/src/hook_runtime.rs)
corroborates child attribution. The exact local schema/probe is stronger evidence
for the current build than assuming nearby source is identical.

The maintained reminder reads at most 256 KiB of the current native transcript
in memory to find unambiguous explicit literal command/workdir hints. Code Mode
nested call IDs are random and transient exec-begin events are not persisted;
this is advisory context, not exact call attribution. Omitted workdir, dynamic
arguments, conflicts and unknown formats do not authorize a cwd guess. No raw
source is retained. Installed readable skill paths are distinguished from native
catalog exposure, which is budgeted. See the
[canonical contract](../../../hooks/README.md#adapt-mainframe-skill-reminder).

The installer retires only the exact receipted experimental registration and
sets its configuration disabled in the same transaction. Original experiment
files/backups remain for recovery and harmless late callbacks. Changed or foreign
registrations are preserved for reconciliation. Normal enable/disable/remove
then follows the maintained hook lifecycle. New registration trust remains a
user action; do not claim active delivery from installer convergence alone.

Trusted live acceptance exposed raw stdout/stderr in Bash `tool_response`, with
no exit status (including failed commands). Advice therefore concerns a bounded
read attempt when success is unknown; known structured failures stay silent.
Raw output is never parsed as status or successful skill-read evidence.

Live acceptance on 2026-10-03 after native user trust: root and a native child
each received a project-method suggestion and a testing-method suggestion, then
a third read produced no further context. The child used an explicit-workdir
relative read for the testing suggestion and read/applied the suggested method
to distinguish synthetic test assertions from native delivery evidence. This
proves those two recipient sequences, not a universal rate of useful selection
or coverage of arbitrary shell syntax. Temporary callback probes were removed.
