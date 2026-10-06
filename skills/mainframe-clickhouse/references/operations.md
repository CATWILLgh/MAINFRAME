# Operations and recovery

## Diagnose before intervening

Observe bounded metadata for the affected tables and nodes: active parts and
bytes, relevant merges/mutations, replication or distribution queues, disk
headroom, query concurrency and selected resource counters. Pick only evidence
that distinguishes the suspected failure. Do not fan out across every replica
merely because a system-table example uses `clusterAllReplicas`.

Use typed parameters through the existing client and its permitted finite
resource profile. For an identified table, these local metadata projections
avoid query text, storage paths and exception contents:

```sql
SELECT mutation_id, create_time, is_done, parts_to_do, latest_fail_time
FROM system.mutations
WHERE database = {db:String} AND table = {table:String}
  AND mutation_id = {mutation:String}
LIMIT 1;

SELECT is_blocked, error_count, data_files, data_compressed_bytes,
       broken_data_files, last_exception_time
FROM system.distribution_queue
WHERE database = {db:String} AND table = {table:String}
LIMIT 20;
```

Check available columns for the installed release. The row limits bound output,
not work. Choose only the relevant query on the verified submitting server or
affected replica; local system tables do not establish cluster-wide completion.
`parts_to_do=0` is not sufficient: an in-flight insert can introduce another part
while `is_done` remains false. An empty distribution queue can mean sent, absent,
wrong node, or no queued work; it does not prove a particular batch arrived.
Correlate its identity with destination/reader evidence. Missing or delayed log
entries likewise do not prove that a timed-out insert wrote nothing.
Sources: [Mutations](https://clickhouse.com/docs/operations/system-tables/mutations),
[Distribution queue](https://clickhouse.com/docs/operations/system-tables/distribution_queue).

Do not run `OPTIMIZE TABLE ... FINAL` as routine cleanup, duplicate removal,
disk-recovery, or a generic fix for slow queries. It rewrites parts and can
bypass ordinary merge-size safeguards. When a specific maintenance task genuinely
requires it, establish its exact scope, capacity and authority; correctness at
read time is a separate query decision.

For too many parts or memory/disk pressure, investigate ingestion, partition
cardinality, queued work and concurrent load. Do not disable protective limits,
increase all background pools, stop merges/replication, or delete storage to
hide symptoms. Restarts, upgrades, `SYSTEM` interventions and Keeper repairs are
explicit operational changes; preserve the project's maintenance owner and
recovery plan.

Cancel only an identified request within the established authority, using a
precise query ID and appropriate scope. Verify cancellation status rather than
assuming the signal stopped work. Killing a mutation leaves already applied
changes in place; inspect the resulting state before recovery.

## Backups and restoration

Replication propagates accidental changes and is not a backup. Before a
destructive production change, establish usable recovery evidence proportionate
to the affected data: covered objects, backup completion, accessible independent
storage, retention and required incremental bases, compatible restore method,
and a tested restoration path. A backup listing alone does not prove recovery.
Do not create another expensive backup when existing verified coverage suffices.

`BACKUP` copies data and consumes resources even when a read-only account can
execute it; its destination and data movement require authority. Preserve secret
delivery through configured mechanisms instead of embedding storage keys in SQL.
`ASYNC` returns before backup/restore completion; observe the specific operation's
terminal status and then verify the requested result.

Prefer a restoration drill into an explicitly authorized isolated destination,
with names and access that cannot overwrite live objects. Verify schema,
representative data, engine/view dependencies, and application read semantics.
Never enable non-empty-target restoration or overwrite production just to test
a backup. A real production restore requires an approved target, writer fencing
where necessary, consistency point, recovery objective and observable acceptance.
Account for external configuration and access definitions not covered by the
selected backup method.

## Capacity and confidentiality

Qualify capacity using representative ingestion, query, merge, replication and
backup/restore loads with headroom. Another database's allocated size is not a
ClickHouse memory/disk estimate. Do not benchmark or load-test production under
diagnostic authority. Prove the actual deployment outcome separately from local
tests, image builds and health responses.

Backups, exports and restored fixtures retain data sensitivity. Follow the
project's access, retention and disposal rules; test placement does not authorize
public exposure or copying production records to a developer laptop.

Sources: [Avoid OPTIMIZE FINAL](https://clickhouse.com/docs/best-practices/avoid-optimize-final),
[KILL](https://clickhouse.com/docs/sql-reference/statements/kill),
[Backup and restore](https://clickhouse.com/docs/operations/backup).
