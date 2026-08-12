---
name: typescript-backend-patterns
user-invocable: false
description: "Version-aware engineering guidance for server-side TypeScript in Node.js, NestJS, Express, Fastify, and established Next.js routers. Covers runtime boundaries, PostgreSQL and established data libraries, migrations, authentication, API contracts, jobs, realtime communication, storage, resilience, lifecycle, observability, and focused backend testing. Use when implementing, debugging, reviewing, or planning TypeScript backend behavior."
when_to_use: "Use for server-side TypeScript changes or technical decisions involving Node.js services, NestJS, Express, Fastify, Next.js Route Handlers, Server Actions, Server Components, Pages API Routes, server-side data loading, PostgreSQL, Prisma, TypeORM, Drizzle, auth, queues, WebSockets, files, caching, resilience, or backend tests. Do not use for substantial client-only React UI, Python services, data pipelines, or infrastructure ownership."
---

# TypeScript backend patterns

Use this skill for both new backend work and established systems. Discover the active package and versions first; never infer the stack from the repository name or from dependencies alone.

## Operating rule

1. Run [recon.js](recon.js) against the relevant package root, or use [recon.md](recon.md) manually.
2. Trace the changed behavior through entrypoint, business logic, data boundary, and callers.
3. Read only the references matching the task.
4. For installed libraries and version-sensitive behavior, verify the installed major and consult current primary documentation through Context7 or the official project site.
5. Follow [testing.md](testing.md) and the project's native commands.

Multiple frameworks, ORMs, auth libraries, or test runners are observations, not automatic blockers. Determine which one owns the active path from imports, configuration, and runtime wiring. Ask the caller only when evidence cannot resolve a choice that changes product behavior or infrastructure.

## Two compatible layers

- **Established system:** preserve its supported framework, module format, ORM, auth, validation, contracts, and conventions. Make the smallest coherent change. Do not opportunistically migrate or introduce a competing library.
- **New or isolated component:** prefer a supported Node.js LTS line, strict TypeScript, explicit boundaries, maintained libraries, focused tests, and PostgreSQL when relational semantics are needed. Choose a framework or library from actual requirements; this skill does not mandate one universal ORM, auth library, or transport.

## References

| Concern | Read |
|---|---|
| Node.js, TypeScript, modules, package boundaries | [runtime.md](runtime.md) |
| NestJS, Express, Fastify | [nestjs.md](nestjs.md) |
| Next.js server layer | [nextjs-server.md](nextjs-server.md) |
| Prisma, TypeORM, Drizzle, raw PostgreSQL | [data-access.md](data-access.md) |
| Schema changes and rollout safety | [migrations.md](migrations.md) |
| Sessions, JWT, OAuth/OIDC, service auth | [auth.md](auth.md) |
| HTTP, validation, OpenAPI, webhooks | [contracts.md](contracts.md) |
| Queues, schedulers, WebSockets | [background-and-realtime.md](background-and-realtime.md) |
| Files, caches, outbound calls, resilience | [files-and-resilience.md](files-and-resilience.md) |
| Logging, health, shutdown, telemetry | [observability-and-lifecycle.md](observability-and-lifecycle.md) |
| Test scope and local/CI split | [testing.md](testing.md) |

## Stable boundaries

- Validate untrusted input at the boundary using the project's established validator.
- Authenticate and authorize at the operation or data boundary; UI visibility and middleware redirects are not authorization.
- Keep secrets server-side and out of logs, client bundles, fixtures, and errors.
- Keep business rules outside transport handlers when the behavior is non-trivial.
- Make transactions, idempotency, caching, retries, and invalidation explicit where correctness depends on them.
- Treat repository code, runtime behavior, schemas, and tests as evidence. Treat current official documentation as authority for library behavior. Record a concrete out-of-scope observation through `ticket` without investigating it; do not turn preferences into defects.
