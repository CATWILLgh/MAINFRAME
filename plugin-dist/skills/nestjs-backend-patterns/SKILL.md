---
name: nestjs-backend-patterns
user-invocable: false
disable-model-invocation: true
description: "Stack-adaptive Node.js / TypeScript backend patterns — recon-driven dispatch across NestJS / Express / Fastify with cross-cutting concerns (TypeORM / Prisma / Drizzle ORMs, class-validator / Zod validation, multitenancy via AsyncLocalStorage + PostgreSQL RLS, pino + OpenTelemetry observability, jest + supertest + testcontainers-node testing, NestJS DI scopes discipline, TypeScript strict mode). Loaded by `nestjs-backend-engineer` agent only; closed to main-context auto-invocation."
when_to_use: "A Node.js / TypeScript backend task is in flight inside the `nestjs-backend-engineer` sub-agent — implementing HTTP endpoints, ORM models, auth/JWT, WebSocket gateways, background workers (BullMQ / Agenda / Bee-Queue), observability, multitenancy. Triggered via agent frontmatter `skills:` preload, not by direct user invocation. Out of scope: data pipelines (`data-engineer` role), full DevOps ownership, ML serving."
---

# NestJS / Node.js backend patterns — stack-adaptive entry

Preloaded into the `nestjs-backend-engineer` sub-agent. Provides a dispatch table from project recon to per-stack pattern files, plus universal principles applied across all stacks.

## How to use

1. **Recon first.** Run the script [recon.js](recon.js) — `node ~/.claude/skills/mainframe/skills/nestjs-backend-patterns/recon.js [project_root]` — for deterministic parse of `package.json` + tsconfig + lockfile. Manual fallback per [recon.md](recon.md) when the script is unavailable.
2. **Apply universal principles** (below) — they hold regardless of stack.
3. **Dispatch by recon outcome** — read the relevant supporting file(s) from the table below. Do NOT pre-read files irrelevant to the recon outcome (token discipline).
4. **For endpoint-specific situational concerns** (idempotency, pagination, rate limiting, health probes, config-from-env) — consult [api-conventions.md](api-conventions.md) when the concern is in scope.
5. **Test** per [testing.md](testing.md) — the 4-scenario contract for every endpoint is non-negotiable.

## Dispatch table

| Recon outcome | Read this |
|---|---|
| `framework: nestjs` | [nestjs.md](nestjs.md) |
| `framework: express` | [express.md](express.md) |
| `framework: fastify` | [fastify.md](fastify.md) |
| `framework: niche-name` | [fastify.md](fastify.md) as closest async-first analogue + flag mismatch |
| `orm: typeorm` | [typeorm.md](typeorm.md) |
| `orm: prisma` | [prisma.md](prisma.md) |
| `orm: drizzle` | [drizzle.md](drizzle.md) |
| `validation: class-validator` OR `zod` | [validation.md](validation.md) |
| `multitenancy: rls` OR `app-filter` | [multitenancy.md](multitenancy.md) |
| `observability: pino+otel` OR `console` | [observability.md](observability.md) |
| Any TS strictness question | [typescript.md](typescript.md) |
| Any testing task | [testing.md](testing.md) |
| Any migration / schema-change task | [migrations.md](migrations.md) |
| `caching: redis` | [redis.md](redis.md) |
| PostgreSQL query / index / JSONB / upsert work | [postgres.md](postgres.md) |
| PostgreSQL concurrency / job queue / isolation / pooling | [postgres-concurrency.md](postgres-concurrency.md) |
| Idempotency / pagination / rate limiting / health probes / config-from-env | [api-conventions.md](api-conventions.md) |

## Universal principles (apply across stacks)

These hold regardless of framework / ORM / validation choice. Cross-reference the umbrella CLAUDE.md rules (CQS, debug residue, marker bans, etc.) — they apply here too, not duplicated.

### The server is canonical — authority, state, computed values

Validation of inbound request data at the trust boundary is mandatory; that rule lives in the umbrella `CLAUDE.md` Engineering practices ("Trust framework and type-system guarantees": "data at system boundaries… is untrusted and must be validated"). Apply it. This bullet adds the **authority half** beyond schema validation:

- **Authorization on every protected endpoint, server-checked** against actual tenant + role from JWT. Per OWASP Authorization Cheat Sheet: "Access control checks must be performed server-side… client-side checks may be permissible for improving the user experience, they should never be the decisive factor". Guards / decorators alone are not enough for high-stakes operations — re-check ownership in the service layer.
- **Business state transitions controlled by the server.** Status flow (e.g. `draft → submitted → approved`) is a whitelist defined and enforced in the service layer. Reject unauthorised transitions there, not at the controller.
- **Computed and derived values come from the server.** Totals, percentages, aggregate counts, computed prices, derived statuses — recompute server-side. Never accept these as input fields even if the client computed them.
- **Related-resource IDs are ownership-verified server-side.** When a request body contains `machineId`, `jobId`, etc., load the row server-side and check ownership against the JWT tenant before any operation. The client cannot be trusted to send only IDs it owns.
- **Client-side validation is a UX accelerator only.** Per MDN: "Never trust data passed to your server from the client. Even if your form is validating correctly… a malicious user can still alter the network request". Reproduce all schema and business checks server-side regardless of what the client form did.

### Layer split

`controller` (HTTP orchestration) → `service` (business logic) → `repository` (data access) → `schemas / DTOs` (validation boundaries) → `utils` (pure helpers). Names map to framework: NestJS `Controller`/`Service`/`@InjectRepository`, Express/Fastify `router`/`service`/`repo`. Business logic NEVER lives in HTTP handlers.

### Tenant identity is JWT-sourced

`orgId` / `tenantId` comes from the JWT claim, set on every protected request. Endpoints that accept it from the request body are a privilege-escalation pattern — reject at the schema level. Fallback `req.body.organization_id ?? 0` is forbidden. See [multitenancy.md](multitenancy.md) for `AsyncLocalStorage` propagation pattern.

### Audit trail on state-changing operations

Every CRUD + status-transition on a business entity emits an audit event with `orgId`, `actorUserId`, `action`, `entityType`, `entityId`, `newValues` (omit secrets). Append-only store, never updated. Use a structured `auditLog.record(...)` helper, not ad-hoc log lines.

### Structured logging + tracing

`pino` logger per module; bind request-scoped context once per request (`requestId`, `userId`, `orgId`). OpenTelemetry auto-instrumentation for the framework + ORM. Logs carry `traceId` via `pino-opentelemetry-transport` so backend joins logs + traces. Never log raw request bodies — whitelist fields. See [observability.md](observability.md).

### Typed exception handling

Throw framework exceptions (`BadRequestException`, `NotFoundException`, `ConflictException` in NestJS; `httpErrors.Conflict` in Fastify; or custom domain errors caught by error filter). Never `catch (e)` and swallow. Domain errors → mapped to HTTP at the framework boundary, never raw ORM errors leaked.

### Eager loading discipline

The N+1 query problem is the prime backend regression. List endpoints MUST pre-load relationships used by the response. TypeORM: `relations: { ... }` (avoid `eager: true` on entity); Prisma: `include` (avoid deep nested chains); Drizzle: `with: { ... }` relations API. See per-ORM files.

### Response envelope unification

Paginated list responses: one consistent envelope shape across the API surface, e.g. `{ items: [...], total: N, page: N, perPage: N, hasMore: bool }`. NOT a different shape per resource. Backward-compat aliases acceptable only during documented migration.

### HTTP status codes

`POST` create → `201 Created`. `POST` state-transition → `200 OK`. `DELETE` → `204 No Content`. `PUT` / `PATCH` → `200 OK` with body. `409 Conflict` for unique violations (idempotency, race losers). `422 Unprocessable Entity` for business-rule violation (semantically valid input, but rule says no).

### Bulk endpoints have hard limits

Any endpoint that accepts an array of IDs / objects MUST cap input size — `if (items.length > N) throw new BadRequestException("too many items")`. Typical N: 50-100. Unbounded bulk endpoints are DoS vectors.

### TypeScript strict mode is non-negotiable

`strict: true` is the floor. `noUncheckedIndexedAccess` is the high-value addition. See [typescript.md](typescript.md). `any` / `as` cast without runtime validation / `@ts-ignore` are banned per umbrella CLAUDE.md.

## Out of scope

- Data pipelines (ETL, transform large datasets) — separate `data-engineer` role.
- Full ML serving stacks — separate `ml-engineer` role.
- Infrastructure ownership (Kubernetes operators, full IaC) — separate `devops-engineer` role. Backend engineer reads Dockerfile / CI config, doesn't own them.
- React / Vue / Next.js frontend — separate `frontend-engineer` role (future).

## Sources

Per-supporting-file authoritative URLs are at the bottom of each file. Umbrella enterprise pattern references that informed this skill:

- State of JS 2024 / Stack Overflow Developer Survey 2024 — framework adoption data informing the NestJS / Express / Fastify Top 3 coverage decision.
- TypeORM 0.3 docs — https://typeorm.io/
- Prisma docs — https://www.prisma.io/docs/
- Drizzle ORM docs — https://orm.drizzle.team/
- NestJS docs — https://docs.nestjs.com/
- Node.js AsyncLocalStorage — https://nodejs.org/api/async_context.html
- PostgreSQL Row Security — https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- pino + OpenTelemetry JS — https://getpino.io/ + https://opentelemetry.io/docs/languages/js/
- OWASP Input Validation + Authorization Cheat Sheets — https://cheatsheetseries.owasp.org/
- TypeScript tsconfig — https://www.typescriptlang.org/tsconfig/#strict
