# PostgreSQL — concurrency, pooling, ops boundary

## Job queue: SKIP LOCKED

`SELECT ... FOR UPDATE SKIP LOCKED LIMIT n` lets each worker claim rows others haven't locked instead of blocking — throughput scales with worker count. Per Postgres this gives "an inconsistent view of the data … not suitable for general purpose work, but … to avoid lock contention with multiple consumers accessing a queue-like table." Use `FOR NO KEY UPDATE` (weaker — won't block FK-share readers) unless you will delete the row. Never use SKIP LOCKED where a consistent full-table view is required.

## Isolation & retry

- **Read Committed** (default): each statement sees a fresh snapshot — two SELECTs in one txn can differ. Fine for most OLTP.
- **Repeatable Read**: a whole-transaction snapshot; a concurrent update makes it fail with SQLSTATE `40001`.
- **Serializable**: emulates serial execution; also fails with `40001` on dependency cycles.
- **Mandatory retry:** anything that can raise `40001` needs an app-side retry loop (also handle `40P01` deadlock) — Postgres won't auto-retry ("it cannot do so with any guarantee of correctness"). At Repeatable Read only *writing* txns raise it; under Serializable even *read-only* txns can, unless declared `SERIALIZABLE READ ONLY DEFERRABLE`. Default to Read Committed; raise isolation only when cross-statement consistency drives a write.

## Connection pooling

- Postgres forks a process per connection (several MB each) — pool, never open per-request. Size to roughly `cores × 2`, not application thread count; more connections ≠ more throughput (engineering convention, not a spec figure).
- **PgBouncer transaction mode** (server connection returned per txn) maximizes reuse but **breaks session state**: use `SET LOCAL`, not `SET` (else config bleeds into the next client). Session-scoped features — advisory locks, `LISTEN`/`NOTIFY`, server-side cursors, pre-1.21 prepared statements — need session mode.

Per-ORM SKIP LOCKED: TypeORM qb `.setLock("for_no_key_update").setOnLocked("skip_locked")`; Prisma raw SQL; Drizzle `.for("update", { skipLocked: true })`. Pool config lives on the DataSource / driver, not per-request.

## Ops boundary — recognize & escalate (not yours to fix)

| Topic | Signal → surface for `devops-engineer` / DBA |
|---|---|
| Partitioning | a single table exceeds RAM; plans scan all partitions despite indexes |
| Autovacuum / bloat | `n_dead_tup` persistently high; `VACUUM` shows up in the slow-query log |
| Replication lag | a replica's `replay_lag` grows under load, or stale reads break invariants |

Surface the signal; do not tune autovacuum or design partitions from application code — that is the `devops-engineer` role.

## Sources

- PostgreSQL — SELECT locking / transaction isolation / serialization failure — https://www.postgresql.org/docs/current/transaction-iso.html
- PgBouncer FAQ — https://www.pgbouncer.org/faq.html
