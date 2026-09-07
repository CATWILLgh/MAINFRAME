# Data access and migrations

## Active data boundary

- Identify the actual database, client or ORM, schema owner, migrations, connection lifecycle, and transaction boundary used by the affected path.
- Preserve the installed data-access mechanism and major version. Do not introduce a second ORM or database abstraction for convenience.
- Select only required fields and relations. Correct demonstrated query or loading problems rather than imposing universal eager loading or repository patterns.
- Parameterize raw queries and preserve the target engine's types, collation, null, transaction, locking, isolation, constraint, and index semantics.
- Use a transaction only when operations must commit or fail together. Verify callback, nested, retry, timeout, and connection semantics for the installed client and version.
- Make concurrency ownership explicit. A read followed by a write is not atomic unless the database contract makes it so.
- Own pools and clients once per intended process or request lifecycle. Prevent connection multiplication in hot-reload, serverless, worker, and test environments.

## Schema and data rollout

- Treat schema and data changes as compatibility and rollout contracts. Determine whether old and new application versions, workers, or clients can overlap.
- Preserve migration ordering and ownership. Do not rewrite an applied migration unless the project's explicit policy permits it.
- Separate compatible expansion, backfill, behavioral switch, and destructive contraction when a one-step change would risk availability or rollback.
- Evaluate locks, table or collection size, index creation, defaults, nullability, validation, transaction support, backfill restartability, and rollback for the actual engine and migration tool.
- Applying migrations or data transformations to a shared or live database requires the corresponding authority. Repository permission alone is insufficient.

Use a real database boundary only when engine-specific semantics are the changed risk and the project layer permits that infrastructure. A substitute database does not prove another engine's queries, migrations, constraints, locks, isolation, or concurrency behavior.

Current owning references: [Prisma documentation](https://www.prisma.io/docs/orm), [TypeORM documentation](https://typeorm.io/docs/), [Drizzle documentation](https://orm.drizzle.team/docs/overview), and [PostgreSQL documentation](https://www.postgresql.org/docs/current/). Use the owning documentation for any other active engine or client.
