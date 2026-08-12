# Data access

- Preserve the active library and installed major: Prisma, TypeORM, Drizzle, `pg`, or `postgres.js`. Do not introduce a second ORM for convenience.
- Read schema, migrations, query code, connection setup, and generated-client ownership before changing data behavior.
- Select only required columns and relations. Fix demonstrated N+1 paths; do not impose universal eager loading.
- Use a transaction only for operations that must succeed or fail together. Confirm the library's exact transaction and retry semantics for the installed version.
- Prisma `$transaction([queryA, queryB])` runs operations sequentially in one transaction; it is not a parallel-query primitive.
- In long-lived Node processes, own pool startup and shutdown once. In serverless or hot-reload environments, prevent accidental client multiplication and use deployment-appropriate pooling.
- Parameterize raw SQL and preserve database-specific semantics. Use real PostgreSQL tests for queries, constraints, indexes, locking, isolation, RLS, and concurrency.

Sources:
- Prisma ORM — https://www.prisma.io/docs/orm
- TypeORM — https://typeorm.io/docs/
- Drizzle ORM — https://orm.drizzle.team/docs/overview
- node-postgres — https://node-postgres.com/
