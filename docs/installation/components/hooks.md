# Adapt hooks

Use this guide for every entry under `components.hooks`. The exact semantic
catalog, trigger contract, failure behavior, attribution model, dependencies,
and representative source cases live in [hooks/README.md](../../../hooks/README.md).
Read that catalog once before adapting the first hook, then revisit only the
active hook section.

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

Ruff, Oxlint, Semgrep, and Fallow are dependencies of their listed hooks, not
separate MAINFRAME components. Prepare them before the active hook's behavior
probe. Reuse compatible installed distributions or install current official
ones only when required. Preserve bounded execution, isolated scanner
configuration, disabled metrics and telemetry, and the catalog's representative
checks. Do not install a tool's own hooks as a substitute for the
MAINFRAME trigger contract.

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
