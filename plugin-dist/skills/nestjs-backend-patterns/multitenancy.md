# Multitenancy patterns (Node)

Same backend concerns as any stack — PostgreSQL RLS at DB layer, propagation of tenant context across async boundaries at app layer. Node's idiomatic mechanism for propagation is `AsyncLocalStorage` (native, since Node 14, improved in Node 24+).

## AsyncLocalStorage — propagation primitive

Per Node docs: «These classes are used to associate state and propagate it throughout callbacks and promise chains. It is similar to thread-local storage in other languages.»

```typescript
import { AsyncLocalStorage } from "node:async_hooks";
export const tenantContext = new AsyncLocalStorage<{ orgId: string; userId: string }>();

// in auth middleware / Fastify preHandler / NestJS guard:
tenantContext.run({ orgId, userId }, () => next());

// anywhere downstream:
const ctx = tenantContext.getStore();
if (!ctx) throw new Error("no tenant context");
```

Anti-pattern: passing `orgId` through every function parameter (parameter drilling) — defeats the purpose of an async context primitive. Set once at auth boundary, read where needed.

## NestJS — `ClsModule` wraps AsyncLocalStorage

Community package `nestjs-cls` provides ergonomic NestJS integration:

```typescript
@Injectable() export class JobsService {
  constructor(private cls: ClsService<{ orgId: string }>) {}
  list() { return this.repo.find({ where: { orgId: this.cls.get("orgId") } }); }
}
```

**Prefer `ClsModule` (AsyncLocalStorage) over REQUEST-scoped providers.** REQUEST scope creates a new instance per request and propagates up the dependency chain — adds overhead AND every consumer becomes request-scoped. AsyncLocalStorage carries state without changing scope semantics.

## PostgreSQL RLS + Node ORM integration

Set tenant context per-request via SQL session GUC:

```typescript
// TypeORM:
await dataSource.query(`SET LOCAL app.current_tenant = $1`, [orgId]);
// Prisma:
await prisma.$executeRaw`SET LOCAL app.current_tenant = ${orgId}`;
```

Then RLS policies `USING (organization_id = current_setting('app.current_tenant')::uuid)` enforce isolation at DB level — defense in depth.

**Critical caveat (PostgreSQL official)**: «Referential integrity checks, such as unique or primary key constraints and foreign key references, always bypass row security». Include `organization_id` in composite UNIQUE indices; review FK relationships for cross-tenant exposure.

## Tenant identity from JWT, never from request body

JWT claim (`orgId`, `userId`) is the only source. Schemas (Zod / class-validator) MUST NOT declare `organization_id` as inbound field. `request.body.organization_id` = privilege-escalation vector.

## Background workers (BullMQ / Agenda / Taskiq-equivalents)

Workers do NOT inherit HTTP request context. Tenant must be passed as a job payload field, set on the worker's tenantContext at job-start, cleared at job-end. Wrap job handler with `tenantContext.run({ orgId }, () => handle(job.data))`.

## Sources

- Node AsyncLocalStorage — https://nodejs.org/api/async_context.html
- PostgreSQL RLS — https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- nestjs-cls — https://github.com/Papooch/nestjs-cls
