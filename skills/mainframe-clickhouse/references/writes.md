# Writes, retries, and schema

## Establish the write boundary

Resolve the exact database/table, engine, partitions or predicate, dependent
views, writer ownership, and relevant shards/replicas before executing a change.
Reuse the caller's bounded write authority. Preview affected data through bounded
reads where needed; an unbounded exact count can itself be too expensive. Agree
on a recovery method adequate to the actual risk before irreversible changes.
Do not treat rollback SQL as guaranteed restoration of original data.

Test syntax and representative behavior on an authorized isolated fixture when
useful. A fixture proves neither production capacity nor cluster completion.
Preserve the deployment or migration owner; do not patch a managed live schema
behind its back. Parameterize values and safely validate/quote identifiers.

For a migration fixture, verify preservation and interpretation of existing
synthetic rows, post-migration writes, and the relevant reader contract. Check
reruns only when the migration promises idempotence; verify teardown touches
only the owned fixture. These are acceptance criteria, not a requirement for
production probes or transactional rollback.

## Ingestion and uncertain outcomes

Prefer appropriate batches or supported asynchronous buffering over many tiny
inserts. Verify actual acknowledgment semantics. With asynchronous inserts,
`wait_for_async_insert=1` waits for flush; zero acknowledges buffering and can
hide later failures or loss. Do not switch to fire-and-forget to suppress errors
or speed up a reliability-sensitive workflow. A flush acknowledgment alone does
not establish every replica's durability or downstream reader visibility.

A network timeout, cancellation, or unknown insert status does not establish
that nothing was written. Before retrying, check the engine, server version,
deduplication settings/window, stable payload or token, and dependent-view
behavior. ClickHouse insert deduplication is conditional and finite; it is not
a universal exactly-once guarantee. `query_id` tracks a request; it is not an
insert deduplication token. Reuse the established ingestion idempotency mechanism.
If the outcome cannot be distinguished safely, record it as uncertain and stop
automatic retries rather than creating guessed duplicates.

Distributed-table buffering is another delivery stage. Identify where the
acknowledgment came from and observe the relevant distribution queue and targets
when end-to-end delivery is the requested result. Do not disable durability or
flush a whole cluster to make a local test appear complete.

## Updates, deletes, and asynchronous work

Choose a supported operation for the actual version and engine; do not assume
new SQL `UPDATE` features exist or enable experimental behavior on production.
`ALTER ... UPDATE/DELETE` can rewrite affected parts and compete with ingestion
and queries. Assess queue depth and headroom before adding mutations. Do not
launch repeated mutations because an earlier one is still pending.

`ALTER ... DELETE` is normally asynchronous; check effective `mutations_sync`.
Track the specific table and mutation ID through `system.mutations`, including
failure and remaining-work state, on the relevant replicas. A timeout waiting
for completion is not rollback. `KILL MUTATION` does not undo completed changes.

Lightweight `DELETE` masks rows; masking completion, query invisibility and
physical removal are different milestones. Effective `lightweight_deletes_sync`
changes acknowledgment timing. Do not promise immediate erasure or disk recovery,
or force merges merely to make that promise true. Physical-erasure requirements
must include replicas, backups, object storage and retention according to the
project's approved policy.

Incremental materialized views process inserted blocks; source updates/deletes
do not generally repair already materialized results. Plan affected target
tables and reader semantics before a source correction or backfill. Verify the
actual view type; refreshable views have different behavior.

## Schema and cluster scope

`ON CLUSTER` widens the target. Use it only for a verified cluster definition and
explicitly covered nodes. Distributed DDL may reach unavailable hosts later and
is not an atomic all-node transaction. Check the relevant DDL queue and resulting
definitions instead of blindly resubmitting after a client timeout. Replicated
database/table behavior may propagate work without an explicit `ON CLUSTER`;
inspect engine/topology rather than treating its absence as proof of local scope.

Drops, truncation, partition removal, TTL changes/materialization, detach/attach,
table exchange, access changes, and recovery writes need their actual scope and
effects established. A time predicate does not make a deletion cheap; a partition
operation affects every row in that partition. Do not lower drop-size guards,
create force-drop flags, disable replication, or grant admin access as shortcuts.

Sources: [Insert strategy](https://clickhouse.com/docs/best-practices/selecting-an-insert-strategy),
[ALTER DELETE](https://clickhouse.com/docs/sql-reference/statements/alter/delete),
[Lightweight DELETE](https://clickhouse.com/docs/sql-reference/statements/delete),
[Distributed DDL](https://clickhouse.com/docs/sql-reference/distributed-ddl),
[Distributed engine](https://clickhouse.com/docs/engines/table-engines/special/distributed),
[Incremental views](https://clickhouse.com/docs/materialized-view/incremental-materialized-view).
