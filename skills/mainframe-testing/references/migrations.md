# Schema and data migrations

Use this method for schema, migration, index, constraint, and data rollout work.
Keep the established engine, ORM, keys, timestamps, and migration conventions;
choose changes from the actual contract rather than universal schema defaults.

## Establish the executable plan

- Inspect the actual schema, shipped migration history, current schema version,
  and normal runner: ordering, transaction boundaries, failure recording,
  connection ownership, and serialization of competing migration processes.
  Preserve shipped or applied migrations; add a forward migration unless the
  project's explicit history policy permits a rewrite.
- Identify server/client versions, app and migration roles, tenant boundaries,
  pooling mode, affected partitions, data size/skew, write rate, and deployment
  overlap. Reuse existing evidence and conventions; name unknowns that change
  the plan. Repository changes confer no authority to migrate a shared database.
- Check old and new readers AND writers, workers, and cron jobs throughout the
  rollout and rollback horizon. For unsafe one-step changes, separate compatible
  expansion, resumable backfill, behavioral switch, and later contraction.
  Define when old behavior can return, when it cannot, and forward recovery.
- Bound backfills by stable checkpoints, batch size, transaction duration, and
  offered load. Handle concurrent writes, retries, partial completion, and
  reconciliation without losing or duplicating data; define stop/resume rules.
- Budget lock wait, execution, held-lock duration, and affected application
  progress per stage. Choose an achievable deployment plan before writing SQL.
  If the requested deadline cannot satisfy availability or rollback, explain
  the conflict and simplest viable staged or maintenance-window option; obtain
  the caller's decision before changing those agreed requirements.

## PostgreSQL: apply only to the inspected server and runner

- `lock_timeout` bounds each lock acquisition, not the entire operation.
  `statement_timeout` includes lock wait. Acquired locks normally survive until
  transaction end: a fast statement can still block traffic until commit.
  Choose both limits from the operation's budget, not copied constants.
- Use `SET LOCAL` only inside an actual transaction. For operations outside a
  transaction, use a dedicated connection or restore session settings on both
  success and failure before pool reuse. Verify the runner's actual behavior.
- `CREATE INDEX CONCURRENTLY` cannot run inside a transaction block. Confirm
  the runner really opts that operation out; a separate file is insufficient.
  It still performs work and waits for transactions/snapshots. Check progress,
  I/O and completion against the budget. Partitioned parents have restrictions;
  use the target version's supported partition/index procedure.
- After an interrupted or failed concurrent build, inspect the index definition
  and validity before repair or retry. An invalid unique index can still enforce
  uniqueness. `IF NOT EXISTS` proves neither validity nor the expected index.
- Before accepting a completed index rollout, compare the installed definition
  with the intended keys/order, expressions, predicate, included columns and
  relevant collation/operator class. Check `pg_index` validity, write readiness
  and live state (`indisvalid`, `indisready`, `indislive`) on the actual target,
  including required partitions. Transitional state during a build/drop is not
  final readiness. Catalog flags do not prove query use or physical integrity;
  use the shared [index checks](performance.md#prove-index-usefulness-and-cost)
  for actual-query applicability and workload benefit.
- Where supported, add a CHECK or foreign key `NOT VALID`, commit the short ADD,
  then VALIDATE separately; validation in the same transaction retains the
  earlier stronger lock. Check the target version's lock and scan behavior.
  A validated CHECK can avoid a later `SET NOT NULL` scan where supported.
- Metadata-only defaults still acquire locks. Verify volatility, rewrite/scan
  behavior, partitions, and target-version support before claiming a change is
  cheap or nonblocking.
- When RLS or tenant-scoped data is relevant, use the actual app role and inspect
  owner/BYPASSRLS/FORCE behavior. RLS alone does not make cross-tenant references
  safe; check references, nullability, and uniqueness. Exercise reads and writes
  with missing, changed, and reused tenant context; transaction-local context
  and pool reset must match actual pooling.

## Replace or retire indexes

Compare full definitions before calling indexes duplicates or treating a wider
index as a replacement. Preserve uniqueness/null semantics, constraint and
replica-identity dependencies, relevant access paths and rollback compatibility.
In PostgreSQL, a foreign key does not automatically index the referencing
columns; assess affected joins and parent updates/deletes rather than blindly
indexing every foreign key.

Zero observed scans alone does not justify removal: check the observation
window/reset, read replicas, rare jobs and integrity purpose. When replacing a
required path, prove the replacement is ready and useful through the
[index checks](performance.md#prove-index-usefulness-and-cost). An obsolete index
can be removed without replacement when evidence establishes it is unnecessary.
Verify affected reads/writes and invariants after removal using the normal
runner and authorized boundary.

## Prove upgrade, compatibility, and bounded disruption

Use the project's [local/CI boundary](local.md) and existing normal migration
runner on the actual engine when its semantics are the risk. Check a clean
history and, for an existing database, upgrade from a representative predecessor
with existing data.
Assert the intended result and protected invariants under actual application
roles, including relevant old/new writers and readers. Test partial failure,
retry, and recovery with no data loss; SQL parsing or ORM generation is not proof.

For contention, use at least two distinct sessions and an explicit barrier to
hold the competing operation. Bound test queries and waits, observe holder and
waiter, assert migration and affected application progress or the defined bounded
failure, and clean up sessions, transactions, and test state on every exit.
An in-memory substitute or single-connection PGlite check does not prove
PostgreSQL concurrency. Use [performance checks](performance.md) for workload
budgets and lock diagnosis; keep expensive compatibility/load work in CI unless
broader local execution is authorized.

Connect the changed guarantee, normal runner, required checks, and pass condition
to the project's verification map. Report observed checks separately from
deployment and live acceptance; name missing evidence and the next check.

## Primary references

Read the matching server version for version-sensitive behavior:

- [PostgreSQL client timeouts](https://www.postgresql.org/docs/current/runtime-config-client.html#RUNTIME-CONFIG-CLIENT-STATEMENT)
  and [SET scope](https://www.postgresql.org/docs/current/sql-set.html).
- [Concurrent index construction](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY).
- [Index readiness catalog](https://www.postgresql.org/docs/current/catalog-pg-index.html)
  and [foreign-key/index behavior](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK).
- [PostgreSQL 16 ALTER TABLE: locks, validation, defaults and scans](https://www.postgresql.org/docs/16/sql-altertable.html).
- [PostgreSQL 16 row security](https://www.postgresql.org/docs/16/ddl-rowsecurity.html)
  and [PgBouncer pooling compatibility](https://www.pgbouncer.org/features.html).

Adaptation reference reviewed alongside these primary sources is the
[database-architect rewrite](https://github.com/davila7/claude-code-templates/pull/1536).
