# Adapt hooks

Use this guide for every entry under `components.hooks`. The exact semantic
catalog, trigger contract, failure behavior, attribution model, dependencies,
and representative source cases live in [hooks/README.md](../../../hooks/README.md).
Read that catalog once before adapting the first hook, then revisit only the
active hook section.

## Reviewed Codex and ZCode events

This table covers Codex Desktop `0.167.0-alpha.4.1` and ZCode Desktop
`3.18.0.10300`. Evidence and activation details are version-specific.
[Codex](../native/codex.md#desktop-01670-alpha41-hook-contract)
[ZCode](../native/zcode-evidence.md#desktop-318010300-hook-contract)

| Canonical hook | Codex | ZCode |
| --- | --- | --- |
| `mainframe-secret-access` | `PreToolUse Bash` denial | `PreToolUse Bash` denial |
| `mainframe-rg-short-replace` | `PreToolUse Bash` advice | `PreToolUse Bash` advice |
| `mainframe-destructive-operations` | `PreToolUse Bash`. Relative checks require a verified local workdir override. | `SessionStart` captures the root. `PreToolUse Bash` checks the actual local cwd. |
| `mainframe-commit-secrets` | `PreToolUse Bash`. Staged inspection requires a verified local workdir override. | `PreToolUse Bash` inspects staged content in the actual local cwd. |
| `mainframe-todo-limits` | `PreToolUse apply_patch` | `PreToolUse Write\|Edit` |
| `mainframe-code-quality` | Pre/post `apply_patch`, then `Stop` or `SubagentStop` | Pre/post `Write\|Edit` with failure cleanup, then `Stop` |
| `mainframe-commit-checkpoint` | `PostToolUse apply_patch` | `PostToolUse Write\|Edit` |
| `mainframe-fallow-quality` | `PreToolUse apply_patch` checks new-file existence. `PostToolUse` emits advice for exact edits. | `PostToolUse Write\|Edit` with exact reconstruction |
| `mainframe-skill-reminder` | Pre/post `Bash` and `SubagentStart` for known roles | Pre/post `Bash` and `PostToolUse Read` in the primary runtime |
| `mainframe-subagent-selection` | `PreToolUse collaborationspawn_agent` when both fields are exposed | Unsupported by the ordinary `Agent` tool's per-call input schema |

Fallow advice stays on the successful edit event because neither reviewed
product offers non-blocking model advice at `Stop`. ZCode ordinary subagents
also lack a runner for these callbacks.

Fresh reviewed Desktop mappings combine quality, Fallow, and checkpoint advice
into one successful-edit callback and one context message. They also combine
Bash guard output and skill advice.
Keep distinct detectors and disable markers behind these private transports.
Isolate detector exceptions so an unavailable advisory cannot suppress a
recognized denial from another detector. Limit combined text to 1600 characters
and serialized output to 8 KiB, allocating space across active channels. A clean
event emits nothing. The post-edit callback has a 20-second native timeout.
Existing Codex split layouts retain native group/handler positions and their
independent controls. ZCode split callbacks with native disable choices retain
that layout and those choices. Replacing Codex hook definitions requires native
trust review during delivery. Source tests alone establish neither trust nor
live receipt.

## Keep native integration thin

Prefer the canonical detector unchanged behind a small installed wrapper. Keep
native event names, payload extraction, output encoding, paths, timeout,
registration, and permissions in that installed wrapper or native settings.
Never add target event schemas to canonical Python sources. For every bound
native tool, resolve its actual input fields, success and failure shape, path
base, and event timing. Do not assume shell edits, patch tools, and dedicated
file editors carry interchangeable payloads.

Canonical behavior does not prescribe one native event name or phase for every
product. Choose the event, or the smallest combination of events, that best
preserves the hook's timing, recipient, evidence, and effect. If an ideal
preventive event cannot safely block while otherwise deferring to the product,
evaluate documented later bindings such as post-action remediation,
completion-time revalidation, or another lifecycle event. Preserve the
strongest useful behavior the product can guarantee and record any lost
prevention or attribution explicitly; do not describe a post-action advisory as
a preventive guard. Reassess the mapping against current native documentation
and runtime evidence instead of copying another adapter's event choices.

Each detector rule has one fixed effect:

- a `guard` runs before the protected effect and is silent or hard-blocking;
- an `advisory` is silent or returns bounded decision-useful context and never
  blocks.

Neither asks permission, grants permission, reads conversational authority, or
changes effect based on role, agent lineage, or topology. Native permission
prompts remain separate.

## Preserve failure behavior

A guard blocks only a positively recognized dangerous condition or a forbidden
command form explicitly defined by the catalog. Missing input,
timeouts, unavailable dependencies, parser limits, wrapper errors, and detector
exceptions must not hard-lock unrelated work. When a protection failure itself
is decision-relevant, use the catalog's distinct non-blocking advisory if the
target supports it; otherwise return no hook decision and record the native
limitation. Leave native permissions authoritative.

Keep clean paths silent. Deduplicate only the scope defined by the catalog.
Never emit secret values, successful-check notices, generic status, raw payloads,
or telemetry.

Cover launch failures as well as detector exceptions. The registered command
or a small retained launcher must handle an unavailable implementation before
importing or invoking it. Do not forward an interpreter's error exit code or
raw stderr as a guard finding or completion continuation. Encode only positively
recognized findings as native denials; use the target's neutral result for
operational failures. A try/except inside a file cannot protect its own absence.

Provide a verified disable path before activation. Prefer native disable
controls that take effect in existing sessions. If a product retains callbacks,
keep their entrypoint callable and make an explicitly disabled MAINFRAME hook
return the native neutral result without loading detectors, scanning, writing
state, injecting context, or requesting continuation. This disables only the
owned hook; it does not grant permission or override another hook. Keep this
small behavior in the adapter, without adding a separate supervisor or service.
Use the [recovery sequence](../problems/rollback-and-recovery.md#retire-hooks-safely)
for disable, replacement, rollback, and removal.

## Concurrency and state

Stateless detectors stay stateless. For `mainframe-code-quality`, preserve one private
temporary state file per adapter namespace, native execution scope, and
workspace with atomic updates and bounded retention. `mainframe-fallow-quality` may reuse
the same proven short-lived attribution mechanics but remains a separate
component and state.

Do not invent product, task, agent, or lineage identifiers. Use only stable
identifiers the native event actually supplies. If exact edit pairing,
attribution, advisory delivery, or completion continuation is unavailable,
record the affected canonical rule as `delivery: unsupported` with its precise
limitation in `reason` instead of scanning the dirty
worktree, guessing by time, or simulating enforcement with a prompt.

Distinguish missing successful-edit pairing from a missing failed-edit callback.
For `mainframe-code-quality`, the catalog permits an unmatched snapshot to expire without
creating a finding. Probe that path before declaring attribution unsupported.
Missing non-blocking completion advice is a separate output limitation; expiry
does not prove that advice can reach its required recipient.

Adapter-owned deduplication must be atomic for one native event, silent on its
redelivery, independent across events and scopes, and temporary. Check expiry
when the same key returns and when old entries follow a large live population;
repeatedly inspecting only one fixed directory prefix can starve cleanup.

## Runtime support

Ruff, Oxlint, Semgrep, yamllint, ShellCheck, actionlint, KubeLinter, Squawk,
and Fallow are hook runtime dependencies. The installer prepares them before
changing hook files or registration. It can reuse a stable executable at the
[tested minimum version](../../../installer/runtime.py) or a newer stable
release that passes a bounded synthetic check through the hook's parser.
If no candidate is compatible, it provisions the tested official release
in shared MAINFRAME-owned user storage. Native archives are verified against
pinned SHA256s for Linux and macOS on x86-64 and ARM64.

The native launchers use the shared runtime path. Plan reports missing support
without mutation. Apply and verify check the actual executable and report its
version. The synthetic checks run during runtime preparation and verification.
Keep hook execution bounded with isolated scanner configuration and disabled
telemetry. Check a new tool release against the full hook suite before raising
the tested minimum or changing the provisioned release.

The Go, Dart, and Rust syntax checks use existing SDK executables. Rust also
discovers local rustup toolchains when `rustfmt` is absent from `PATH`. A
missing SDK produces one advisory per execution scope when a file of that
language is edited.

Product uninstall retains this shared runtime because another MAINFRAME adapter
may still use it.

## Verify

Run these native event and lifecycle checks during adapter development or
explicitly requested acceptance, not as an ordinary maintained-installation
tail.

Run canonical regressions first without installing tests globally. Then prove
native event delivery, payload filtering, clean silence, safe finding behavior,
operational failure behavior, context bounds, and the required advisory or
blocking effect. Use synthetic payloads and isolated temporary files or Git
repositories. Never test destructive behavior against a real root, home, or
project path.

The local regression routes are `python3 -B -m unittest discover -s hooks/tests`
for canonical behavior and `python3 -B -m unittest discover -s tests` for
adapters and lifecycle. Their cases cover duplicate callbacks, bounded scanner
waits, nonregular files, disabled legacy layouts, per-detector fault isolation,
Unicode wire budgets, and multi-channel consolidation. Native installed-build
contract tests remain separate from disposable source fixtures and can reject
an unreviewed application upgrade.

For edit-dependent hooks, perform a real harmless native edit, observe the
newly introduced finding, repair it, and prove the finding clears. For a
completion guard, also prove the blocked completion and subsequent release.
Exercise each materially different bound tool payload and failed-edit path; a
synthetic normalized dictionary does not prove native extraction or attribution.
For `mainframe-fallow-quality`, prove exact scope attribution and advisory delivery; do not
require a completion block for this advisory.

Verify primary and subagent delivery when both are supported execution paths.
Confirm the responsible agent receives actionable context once, unrelated scopes
remain silent, and the wrapper uses identities supplied by that runtime. Probe
concurrent scopes where the hook retains attribution state. Missing scope proof
leaves verification pending; proven missing native attribution makes delivery
unsupported.

A completion hook that can continue the model must have a finite native or
adapter-owned repetition bound. Use a documented re-entry or execution identity
to prevent the same finding from autonomously continuing one execution forever;
retain unresolved state for a later user turn or execution. Verify the first
positive continuation, the repeated-event stop, a later execution's recheck,
and release after repair. A missing implementation or detector failure remains
neutral at every repetition.

If both Desktop and CLI are explicitly requested and dispatch hooks differently,
verify each under the [surface rule](../verification.md#desktop-and-cli). A detector unit test
does not prove native registration. In an isolated native scope, retain the
previous callback command while disabling its hook and removing its detector
body. Prove repeated tool and completion callbacks remain neutral and produce
no injected feedback. Also probe a missing implementation and interpreter
failure while enabled, and confirm a real guard finding still blocks. Prove
reload drops the obsolete callback before removing its entrypoint. A simulated
dispatcher is useful source evidence but does not establish native unloading.
Keep missing lifecycle proof at `verification: pending`. Remove probe-owned temporary state and
registrations through the [recovery guide](../problems/rollback-and-recovery.md).
