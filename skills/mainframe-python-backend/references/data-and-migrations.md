# Data and migrations

Use the project's actual data layer and database semantics. Do not assume PostgreSQL, SQLAlchemy, Django ORM, or any other engine or library. Trace the query, transaction owner, constraints, isolation behavior, connection lifecycle, callers, and externally visible outcome.

Keep a unit of work bounded to one request, job, or explicit operation unless the library documents another safe pattern. For SQLAlchemy, do not share `Session` or `AsyncSession` instances across concurrent threads or tasks; keep factory lifetime distinct from session lifetime. After a failed flush or transaction, follow the library's required rollback and cleanup behavior.

Make atomicity explicit. Keep related writes and state transitions in the intended transaction, and schedule irreversible side effects only at the correct commit boundary. Use constraints and atomic operations for invariants that concurrent writers can violate; application checks alone may race.

Release transactions and pool slots before waiting for a queue, quota, or
upstream response whenever the protocol permits. For contention, measure the
holder, waiter, and affected request progress on the actual engine.

Review loading strategy and query count at the affected path. Avoid accidental lazy I/O after a session closes, implicit I/O in async code, unbounded reads, per-row queries, and serialization that changes query behavior.

For query optimization or index design/usefulness, use the shared
[index checks](../../mainframe-testing/references/performance.md#prove-index-usefulness-and-cost).
Verify the actual ORM/client SQL and bindings; model declarations or literal-only
queries do not prove index applicability or a read/write performance improvement.

For schema, migration, index, constraint, or backfill changes, use the shared
[migration method](../../mainframe-testing/references/migrations.md). Inspect the
active framework's migration graph, generated operations, transaction settings,
and actual runner; ORM declarations alone do not establish database behavior.

Run against the real database engine only when engine-specific behavior is the risk and the project layer and current authority allow it. A lightweight substitute is not proof of dialect, isolation, locking, constraint, or migration behavior.
