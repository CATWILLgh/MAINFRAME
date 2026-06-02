# Prisma patterns

Most-adopted Node ORM for traditional / NestJS backends. `schema.prisma` is the source of truth — schema-first with generated TypeScript client. Prisma 7 (2026) rewrote internals from Rust to TypeScript; cold-start latency dropped materially vs the prior Rust-engine releases (per encore.dev's 2026 benchmark: ~320ms cold start vs ~1200ms before).

## Schema + client generation

- One `schema.prisma` per project; models declared with `model User { ... }` syntax.
- After schema change: `npx prisma generate` → regenerates client. Required after every schema edit before code uses new types.
- `npx prisma migrate dev --name <description>` — generates SQL migration + applies in dev.
- `npx prisma migrate deploy` — applies pending migrations in prod (no client regen).
- **Zero-downtime safety — non-blocking DDL, expand-contract, batched backfills: see [migrations.md](migrations.md).**

## Client usage

```typescript
const prisma = new PrismaClient();
const job = await prisma.job.findUnique({
  where: { id },
  include: { downtimes: true, machine: { include: { shop: true } } },
});
```

- `findUnique` for PK lookup, `findFirst` for non-unique, `findMany` for collections.
- `include` for eager loading; `select` for column reduction. **Anti-pattern**: deep nested `include` chains explode query plan and response payload.

## Transactions

```typescript
await prisma.$transaction(async (tx) => {
  await tx.shift.update({ where: { id }, data: { status: "active" } });
  await tx.auditLog.create({ data: { entity: "Shift", entityId: id, action: "ACTIVATE" } });
});
```

Interactive txn — multi-statement atomic. For independent batches, use array form: `prisma.$transaction([op1, op2])` — parallel SQL.

## Locking

Prisma does not expose `SELECT FOR UPDATE` directly. Use raw query:

```typescript
const rows = await prisma.$queryRaw`SELECT * FROM "Shift" WHERE id = ${id} FOR UPDATE`;
```

Wrap the raw query + subsequent update in an interactive txn (`$transaction`) — lock scope is the txn.

## Connection pooling

Prisma client creates its own pool. **Critical** in serverless: every cold start = new pool. Use Prisma Accelerate or external pooler (PgBouncer transaction mode) for serverless.

## Sources

- Prisma docs — https://www.prisma.io/docs/
- encore.dev 2026 ORM benchmark (Prisma vs Drizzle vs TypeORM) — https://encore.dev/articles/prisma-vs-drizzle-vs-typeorm
