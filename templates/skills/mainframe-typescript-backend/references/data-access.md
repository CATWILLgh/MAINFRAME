# Data access

- Preserve the active library and installed major: Prisma, TypeORM, Drizzle,
  `pg`, or `postgres.js`. Do not introduce a second ORM for convenience.
- Read schema, migrations, query code, connection setup, and generated-client
  ownership before changing data behavior.
- Select only required columns and relations. Fix demonstrated N+1 paths rather
  than imposing universal eager loading.
- Use a transaction only when operations must succeed or fail together. Verify
  exact transaction and retry semantics for the installed library version.
- Do not treat Prisma `$transaction([a, b])` as parallel query execution.
- Own pool startup and shutdown once in long-lived processes. In serverless or
  hot-reload environments, prevent client multiplication and use appropriate
  pooling.
- Parameterize raw SQL and preserve PostgreSQL semantics. Use real PostgreSQL
  for queries, constraints, indexes, locks, isolation, RLS, and concurrency.

Sources: [Prisma](https://www.prisma.io/docs/orm),
[TypeORM](https://typeorm.io/docs/),
[Drizzle](https://orm.drizzle.team/docs/overview),
[node-postgres](https://node-postgres.com/).
