---
name: mainframe-typescript-backend
description: Implement, debug, review, or plan server-side TypeScript in Node.js services, NestJS, Express, Fastify, and established Next.js server layers. Use for HTTP APIs, business logic, PostgreSQL, Prisma, TypeORM, Drizzle, auth, migrations, workers, queues, realtime communication, storage, resilience, observability, and backend tests. Do not use for substantial client-only React UI, Python services, data pipelines, or infrastructure ownership.
---

# TypeScript backend engineering

Discover the active package and installed stack before choosing an approach.
Never infer the framework, router, runtime, ORM, or test path from a repository
name or dependency list alone.

## Work sequence

1. Run `node scripts/recon.js <package-root>` from this skill, or follow
   [recon.md](references/recon.md) manually.
2. Trace the affected behavior through its entrypoint, business rules, data or
   external boundary, callers, and observable output.
3. Read only the references matching the active path and changed risk.
4. Verify installed versions and version-sensitive behavior through current
   primary documentation or Context7.
5. Use the project's native commands and the smallest faithful red-to-green
   test. Read [testing.md](references/testing.md) when selecting a test level,
   changing existing tests, or separating local and CI checks.

Several frameworks, ORMs, validators, auth libraries, or test runners are
observations, not automatic blockers. Resolve the active owner from imports,
configuration, runtime wiring, and affected files. Escalate only an unresolved
choice that changes product behavior, infrastructure, permissions, or the
assigned result.

Complete the assigned behavior. Do not substitute TODOs, placeholders, skipped
or weakened tests, suppressions, or deferred in-scope work for implementation.

## Preserve or introduce deliberately

- In an established system, preserve its supported runtime, framework, module
  format, ORM, auth, validation, contracts, and conventions. Make the smallest
  coherent change; do not add a competing library or incidental migration.
- In a new isolated component, prefer a supported Node.js LTS line, strict
  TypeScript, explicit boundaries, maintained libraries, focused tests, and
  PostgreSQL when relational semantics are required. Select libraries from the
  real requirements rather than a universal preferred stack.

## Reference routing

| Changed concern | Read |
|---|---|
| Node.js, TypeScript, modules, packages, runtimes | [runtime.md](references/runtime.md) |
| NestJS, Express, Fastify | [frameworks.md](references/frameworks.md) |
| Next.js server code | [nextjs-server.md](references/nextjs-server.md) |
| HTTP, validation, OpenAPI, webhooks | [contracts.md](references/contracts.md) |
| Sessions, JWT, OAuth/OIDC, service auth | [auth.md](references/auth.md) |
| Prisma, TypeORM, Drizzle, raw PostgreSQL | [data-access.md](references/data-access.md) |
| Schema and data rollout | [migrations.md](references/migrations.md) |
| Queues, schedulers, WebSockets | [background-and-realtime.md](references/background-and-realtime.md) |
| Files, caches, outbound calls, resilience | [files-and-resilience.md](references/files-and-resilience.md) |
| Logging, health, shutdown, telemetry | [observability-and-lifecycle.md](references/observability-and-lifecycle.md) |
| Test scope, cost, and local/CI split | [testing.md](references/testing.md) |

## Stable boundaries

- Validate untrusted input at the real boundary with the established validator.
- Authenticate and authorize the concrete operation or data access server-side.
- Keep secrets server-side and out of logs, client payloads, fixtures, and errors.
- Keep non-trivial business rules outside transport handlers.
- Make transactions, idempotency, cache invalidation, retries, and side effects
  explicit where correctness depends on them.
- Treat repository code, runtime behavior, schemas, and tests as local evidence;
  use current owning documentation for external behavior.
- Record a concrete out-of-scope problem through `mainframe-ticket` without
  investigating it. Do not turn preferences into defects.
