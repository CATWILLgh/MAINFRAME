---
name: mainframe-typescript-backend
description: Design, change, debug, or review Node.js TypeScript services and Next.js server code, including APIs, Server Actions, databases, migrations, workers, and tests.
---

# TypeScript backend engineering

Apply within the immediate caller's scope and authority, whether implementing, delegated, or reviewing.

For behavior changes, load `mainframe-testing` for the shared TDD and local/CI boundary, then use this skill's testing reference for stack-specific evidence.

For schema, migration, index, or constraint work, use the shared
[migration method](../mainframe-testing/references/migrations.md) alongside the
data reference below.

## Establish the active server boundary

Identify the package that owns the affected behavior. If ownership or runtime wiring is unclear, use the bounded [recon script](scripts/recon.mjs) or [manual reconnaissance](references/recon.md) for that package. Reuse current inspected evidence; declared dependencies and filenames do not prove the active runtime path.

Trace the requested behavior through its real entrypoint, runtime validation, business rules, data or external boundary, side effects, callers, and observable output. Inspect the effective project instructions and use only infrastructure authorized by effective instructions or the immediate caller.

Several frameworks, routers, validators, database clients, or test runners may legitimately coexist. Resolve ownership from imports, registration, configuration, entrypoints, runtime wiring, and affected files. Surface a decision only when evidence cannot resolve a product, business, data, infrastructure, permission, or authority choice with material consequences.

## Preserve the established system

Preserve the active runtime, package manager, framework, module format, architecture, validation, authentication, persistence, contracts, observability, and testing conventions unless changing one is part of the assigned result. Do not introduce a competing library, broad strictness migration, new service, or infrastructure dependency for convenience.

For a genuinely new isolated component, derive the stack from its requirements, supported runtime, operational environment, and project decisions. Do not impose a universal framework, ORM, database, queue, or deployment model.

Verify installed versions before relying on version-sensitive behavior. Prefer the owning project's current primary documentation. An available documentation service may locate that corpus, but repository code and runtime evidence remain authoritative for project-owned behavior.

## Load only the relevant detail

| Changed concern | Read |
|---|---|
| Package, runtime, TypeScript, modules, monorepos, or generated ownership | [runtime](references/runtime.md) |
| NestJS, Express, Fastify, or another established Node server | [frameworks](references/frameworks.md) |
| App Router, Pages Router, Route Handlers, Server Actions, or server rendering | [Next.js server layer](references/nextjs-server.md) |
| HTTP or event contracts, validation, authentication, authorization, or webhooks | [contracts and security](references/contracts-and-security.md) |
| Database access, transactions, concurrency, schema changes, or data rollout | [data and migrations](references/data-and-migrations.md) |
| Queues, schedulers, workers, WebSockets, or event delivery | [background and realtime](references/background-and-realtime.md) |
| Files, object storage, outbound calls, retries, rate limits, or caches | [files, cache, and resilience](references/files-cache-and-resilience.md) |
| Logging, metrics, tracing, readiness, shutdown, or resource ownership | [observability and lifecycle](references/observability-and-lifecycle.md) |
| Choosing focused backend evidence or a real dependency boundary | [testing](references/testing.md) |

## Complete and verify the assigned result

Make the smallest complete change across every affected location inside the assigned boundary. Keep non-trivial business rules independent of transport when the established architecture supports that separation. Validate untrusted data at the real runtime boundary, authorize the concrete action and resource server-side, and make transactions, retries, idempotency, cache invalidation, and side effects explicit when correctness depends on them.

Use project-native commands: obtain faithful red evidence under the shared testing method, then run the focused proof and nearest relevant fast checks. Real database, broker, storage, browser or deployed checks require that boundary's semantics to be the risk and the shared local/CI and authority boundary to permit them.

Do not substitute TODOs, placeholders, weakened types or assertions, skipped checks, suppressed failures, compatibility debris, or unrecorded follow-ups for completed work. Report observed checks and material gaps. Protect secrets across source, bundles, logs, errors, fixtures, telemetry, serialization, and command traces; preserve unrelated work. Record or reconcile concrete authorized out-of-scope findings through the project route, then resume the assignment without expanding investigation.
