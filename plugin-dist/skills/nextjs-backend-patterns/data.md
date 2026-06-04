# Data — ORM in a serverless context

The Next-specific data concern is **connection management**, not query syntax (generic ORM depth lives in the standalone backend skill).

## Prisma — singleton, or you exhaust the pool

- **One global `PrismaClient`, reused.** Dev hot-reload and serverless cold-starts otherwise create a new client per invocation and exhaust DB connections. Per Prisma: *"Creating multiple instances can exhaust your database's connection limit and slow down queries."*
- The pattern (`lib/db.ts`, marked `import 'server-only'`): keep the client on `globalThis` in dev, fresh in prod —
  `export const db = globalThis.__db ?? new PrismaClient()`
  `if (process.env.NODE_ENV !== 'production') globalThis.__db = db`

## Serverless pooling

- Per Prisma: *"every invocation may result in a new connection… run out of open connections."* Use a pooler — **PgBouncer**, **Prisma Accelerate**, or a `connection_limit` on the URL. Direct DB + serverless with no pooler = stalls.
- **Drizzle**: prefer HTTP / serverless drivers (Neon, PlanetScale, Turso) over a raw TCP pool in a serverless runtime.

## Discipline

- Eager-load relations (N+1 is the prime backend regression). Validate inputs (Zod) before queries. Authorize in the DAL **before** the query, not after.

## Sources

- Prisma best practices (singleton) — https://www.prisma.io/docs/orm/more/best-practices
- Prisma serverless / Vercel (pooling, connection exhaustion) — https://www.prisma.io/docs/orm/prisma-client/deployment/serverless/deploy-to-vercel
