---
name: mainframe-typescript-backend
description: Develop, debug, review, or test server-side TypeScript in Node.js services and established Next.js server layers. Use proactively for backend APIs, business rules, persistence, jobs, realtime behavior, server integrations, and focused backend tests. Do not use for substantial client-only UI, Python services, data or ML pipelines, or infrastructure ownership.
---

# TypeScript backend engineering

Apply this method whenever the active work matches the description, whether you are the primary implementer, a delegated engineer, or a reviewer. Follow the scope and authority supplied through the current execution path; this skill does not expand either.

## Establish the active server boundary

Identify the nearest package that owns the affected behavior. Run the bounded [recon script](scripts/recon.mjs) against that explicit package root, or follow [manual reconnaissance](references/recon.md). Treat the report as routing evidence, not as a decision engine: declared dependencies, filenames, and repository names do not prove the active runtime path.

Trace the requested behavior through its real entrypoint, runtime validation, business rules, data or external boundary, side effects, callers, and observable output. Inspect the effective project instructions and use only the infrastructure allowed by the project layer.

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

Use the project's native commands and the smallest faithful failing evidence when a behavior change can be demonstrated before implementation. Then run the focused proof and the nearest relevant fast checks that protect the changed risk. Use a real database, broker, storage service, browser, or deployed boundary only when its semantics are the risk and the effective project instructions and current authority permit it.

Do not replace completion with TODOs, placeholders, weakened types or assertions, skipped checks, suppressed failures, compatibility debris, or an unrecorded follow-up. State what was actually observed and every material verification gap.

Keep secrets out of source, bundles, logs, errors, fixtures, telemetry, serialized output, and command traces. Preserve unrelated work. When a concrete out-of-scope project problem remains, record or reconcile it through the available project problem route when authorized, then return to the assigned result without expanding the investigation.
