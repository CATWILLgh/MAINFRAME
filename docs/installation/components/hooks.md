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
Never add target event schemas to canonical Python sources.

Each detector rule has one fixed effect:

- a `guard` runs before the protected effect and is silent or hard-blocking;
- an `advisory` is silent or returns bounded decision-useful context and never
  blocks.

Neither asks permission, grants permission, reads conversational authority, or
changes effect based on role, agent lineage, or topology. Native permission
prompts remain separate.

## Preserve failure behavior

A guard blocks only a positively recognized dangerous condition. Missing input,
timeouts, unavailable dependencies, parser limits, wrapper errors, and detector
exceptions must not hard-lock unrelated work. When a protection failure itself
is decision-relevant, use the catalog's distinct non-blocking advisory if the
target supports it; otherwise allow the original action and record the native
limitation.

Keep clean paths silent. Deduplicate only the scope defined by the catalog.
Never emit secret values, successful-check notices, generic status, raw payloads,
or telemetry.

## Concurrency and state

Stateless detectors stay stateless. For `code-quality`, preserve one private
temporary state file per adapter namespace, native execution scope, and
workspace with atomic updates and bounded retention. `fallow-quality` may reuse
the same proven short-lived attribution mechanics but remains a separate
component and status.

Do not invent product, task, agent, or lineage identifiers. Use only stable
identifiers the native event actually supplies. If exact edit pairing,
attribution, advisory delivery, or completion continuation is unavailable,
record the affected canonical rule as unsupported instead of scanning the dirty
worktree, guessing by time, or simulating enforcement with a prompt.

## Runtime support

Ruff, Oxlint, Semgrep, and Fallow are dependencies of their listed hooks, not
separate MAINFRAME components. Reuse compatible installed distributions or
install current official ones only when required. Preserve bounded execution,
isolated scanner configuration, disabled metrics and telemetry, and the catalog's
representative checks. Do not install a tool's own hooks as a substitute for the
MAINFRAME trigger contract.

## Verify

Run canonical regressions first without installing tests globally. Then prove
native event delivery, payload filtering, clean silence, safe finding behavior,
operational failure behavior, context bounds, and the required advisory or
blocking effect. Use synthetic payloads and isolated temporary files or Git
repositories. Never test destructive behavior against a real root, home, or
project path.

If Desktop and CLI dispatch hooks differently, verify both. A detector unit test
does not prove native registration.
