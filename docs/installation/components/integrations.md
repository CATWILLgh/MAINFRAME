# Adapt integrations, runtime, settings, and permissions

Use this guide for `mcp`, `plugins`, `runtime`, `settings`, and for native support
required directly by another listed component.

## Inventory remains authoritative

An empty category means MAINFRAME currently installs no component of that kind.
Do not populate it from available marketplaces, old adapters, archives, or
nearby configuration. A runtime executable required by a listed hook or skill
is support for that component and has no separate inventory row.

Reuse compatible native tools and runtimes. Install only what an active listed
component requires. Never install development harnesses, test fixtures,
telemetry collectors, optional integrations, or generated adapters by default.

## Analyzer ownership

[Small tool profiles](../../../skills/mainframe-testing/references/tooling.md)
own project analyzer selection and execution policy. The maintained
[hook runtime installer](../../../installer/runtime.py) owns dependencies of
registered MAINFRAME hooks. Its catalog is a tested hook contract, not a
universal project language catalog. Do not install a language tool merely
because its ecosystem exists somewhere on the machine, or substitute a
project analyzer without checking the hook's flags and output semantics.

Provision required hook executables before activating their registrations.
Keep package download/update logic out of hook execution. Verify compatible
availability and the adapter's relevant analyzer contract; report unavailable
checks distinctly from clean results. Reuse compatible installations through
the maintained installer and preserve unrelated project environments.
SonarQube and comparable server/hosted platforms are not default dependencies;
adding them requires an explicit user request and an agreed operating scope.

## Shared OpenSpec CLI

The [OpenSpec skill](../../../skills/mainframe-openspec/SKILL.md) uses one CLI
per user. Full installation through Codex, ZCode, MiniMax Code, or Cline prepares
it through the [shared runtime installer](../../../installer/runtime.py).
For an existing compatible Desktop installation, `plan`, `apply`, and `verify`
with `--surface desktop --skill mainframe-openspec` use the same runtime. Run the
scoped `apply` with any supported Desktop adapter to prepare the CLI. Repeat it
for the other adapters when their skill copies need updating.

The installer reuses a compatible OpenSpec or installs the pinned official npm
package into user storage. The npm route requires Node.js 22.12.0 or newer and
npm. The launcher at `~/.local/share/mainframe/runtime/bin/openspec` works with
the shell path inherited by Desktop applications. It opts out of telemetry and
update checks. Use MAINFRAME to update the managed CLI. Each project still owns
its OpenSpec artifacts and can select its own approved executable.

`plan` reports runtime readiness without provisioning. `apply` prepares the CLI
before writing the skill. `verify` requires both file convergence and a working
CLI. The shared runtime remains available after removing one adapter.

## MCP and external capabilities

Prepare protected credential delivery before registering a server. Use the
target's documented field names and secret references. Merge by stable server
identity and preserve unrelated registrations.

During adapter development or explicitly requested acceptance, verify native
discovery and a harmless capability listing without printing
commands, headers, tokens, environment values, or protected paths. A process
that starts successfully does not prove tool exposure or authentication.

## Permissions

Apply the narrowest global permission that represents the canonical component's
actual boundary. A prompt rule is not a replacement for an enforceable native
permission. Record what is enforced and what remains instructional.

For `mainframe-harness-feedback`, grant access only to
`<MAINFRAME_ROOT>/docs/tickets/open/observations/` when the product can express
that path. Do not grant the whole repository, and do not create the directory
until the first real report requires it.

Never weaken a user's broader security policy to make MAINFRAME pass. If a
required capability conflicts with managed policy, preserve the policy. Keep
delivery `pending` with the missing decision in `next_action`, or set delivery
to `unsupported` with the established product limitation in `reason`.

## Settings and cleanup

Merge settings by stable native key. Preserve user-owned values and effective
precedence. Remove an obsolete MAINFRAME-owned registration only after its
replacement is natively verified. Keep application caches and session data;
remove only installation staging and positively identified residue.
