# PostgreSQL concurrency and pooling

Use real PostgreSQL tests when the result depends on locking, isolation, constraints, pooling, or concurrent writes.

## Transactions and retries

- Keep the invariant check and its write in one transaction. Choose row locks, an atomic statement, a constraint, optimistic versioning, or serializable execution from the actual contention and invariant.
- `SKIP LOCKED` is useful for queue-like consumers that may intentionally skip claimed rows. It produces an inconsistent view and is not a general pagination or reporting tool.
- PostgreSQL can abort transactions with serialization failure `40001` or deadlock `40P01`. Retry the complete transaction only when its inputs and external side effects make retry safe; bound retries and surface exhaustion.
- Raising isolation does not replace a correct retry and side-effect design.

## Pooling

- Reuse bounded connections and size the pool from database capacity, instance count, workload, and measurements. A fixed cores-based formula is not a portable truth.
- With PgBouncer transaction pooling, transaction-local state is safer than session state. Check compatibility for prepared statements, advisory locks, temporary tables, server-side cursors, and listen/notify against the installed PgBouncer version and client behavior.
- Keep tenant context and transaction lifetime aligned so pooled connections cannot leak state.

## Operational boundary

Application work may expose autovacuum pressure, bloat, replication lag, saturation, or partition-pruning problems. Return the evidence to the immediate caller for infrastructure or DBA handling rather than silently changing server settings from application code.

## Sources

- PostgreSQL transaction isolation — https://www.postgresql.org/docs/current/transaction-iso.html
- PostgreSQL explicit locking — https://www.postgresql.org/docs/current/explicit-locking.html
- PostgreSQL SELECT locking — https://www.postgresql.org/docs/current/sql-select.html
- PgBouncer features — https://www.pgbouncer.org/features.html
