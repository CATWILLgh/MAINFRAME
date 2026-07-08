# Drizzle ORM patterns

Code-first ORM with no generation step. Per encore.dev's 2026 ORM benchmark: ~7.4kb bundle vs Prisma's ~180kb — ideal for serverless / edge / bundle-sensitive deployments. Rapidly growing adoption (2024-2026).

## Schema as code

Schema defined directly in TypeScript:

```typescript
import { pgTable, serial, text, timestamp } from "drizzle-orm/pg-core";
export const jobs = pgTable("jobs", {
  id: serial("id").primaryKey(),
  status: text("status").notNull(),
  createdAt: timestamp("created_at").defaultNow(),
});
```

No `schema.prisma`, no codegen. Types flow from the schema declaration directly to query results.

## Query builder

```typescript
import { eq, and, desc } from "drizzle-orm";
const rows = await db.select().from(jobs)
  .where(and(eq(jobs.machineId, mid), eq(jobs.status, "active")))
  .orderBy(desc(jobs.createdAt)).limit(50);
```

SQL-like API surface. For joins: `.leftJoin(machines, eq(jobs.machineId, machines.id))`. Drizzle returns flat row objects — manual mapping to nested shape if needed.

## Relations API

For nested queries (similar to Prisma `include`):

```typescript
const job = await db.query.jobs.findFirst({
  where: eq(jobs.id, id),
  with: { downtimes: true, machine: { with: { shop: true } } },
});
```

Define `relations(...)` config separately from table — explicit declaration of FKs and cardinality.

## Migrations

- `drizzle-kit generate` → SQL files in `drizzle/` dir from schema diff.
- `drizzle-kit migrate` → applies in dev.
- For prod: run SQL files via your migration runner of choice; Drizzle does not enforce migration lifecycle.
- **Zero-downtime safety — non-blocking DDL, expand-contract, batched backfills: see [migrations.md](migrations.md).**

## Transactions + locking

```typescript
await db.transaction(async (tx) => {
  const [shift] = await tx.select().from(shifts)
    .where(eq(shifts.id, id)).for("update");
  if (shift.status === "completed") throw new Error("already completed");
  await tx.update(shifts).set({ status: "active" }).where(eq(shifts.id, id));
});
```

`.for("update")` = `SELECT FOR UPDATE`. Lock scope is the transaction.

## Sources

- Drizzle ORM docs — https://orm.drizzle.team/
- encore.dev 2026 ORM benchmark — https://encore.dev/articles/prisma-vs-drizzle-vs-typeorm
