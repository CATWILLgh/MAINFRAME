# Data access and migrations

## Active data boundary

- Identify the actual database, client or ORM, schema owner, migrations, connection lifecycle, and transaction boundary used by the affected path.
- Preserve the installed data-access mechanism and major version. Do not introduce a second ORM or database abstraction for convenience.
- Select only required fields and relations. Correct demonstrated query or loading problems rather than imposing universal eager loading or repository patterns.
- Parameterize raw queries and preserve the target engine's types, collation, null, transaction, locking, isolation, constraint, and index semantics.
- Use a transaction only when operations must commit or fail together. Verify callback, nested, retry, timeout, and connection semantics for the installed client and version.
- Make concurrency ownership explicit. A read followed by a write is not atomic unless the database contract makes it so.
- Own pools and clients once per intended process or request lifecycle. Prevent connection multiplication in hot-reload, serverless, worker, and test environments.
- Release transactions and pool slots before waiting for a queue, quota, or upstream response whenever the protocol permits. Measure the lock holder, waiter, and request progress on the actual engine when changing contention.

For query optimization or index design/usefulness, use the shared
[index checks](../../mainframe-testing/references/performance.md#prove-index-usefulness-and-cost).
Verify emitted client/ORM SQL, bindings and prepared-query behavior; declarations
or an index added successfully do not prove application use or workload benefit.

## Schema and data rollout

Use the shared [migration method](../../mainframe-testing/references/migrations.md)
for schema, migration, index, constraint, or backfill changes. Inspect generated
SQL and the actual CLI or deployment runner, including transaction opt-outs;
client schema declarations and a separate migration file do not prove execution
semantics.

Applying migrations or data transformations to a shared or live database requires the corresponding authority. Repository permission alone is insufficient.

Use a real database boundary only when engine-specific semantics are the changed risk and the project layer permits that infrastructure. A substitute database does not prove another engine's queries, migrations, constraints, locks, isolation, or concurrency behavior.

Current owning references: [Prisma documentation](https://www.prisma.io/docs/orm), [TypeORM documentation](https://typeorm.io/docs/), [Drizzle documentation](https://orm.drizzle.team/docs/overview), and [PostgreSQL documentation](https://www.postgresql.org/docs/current/). Use the owning documentation for any other active engine or client.
