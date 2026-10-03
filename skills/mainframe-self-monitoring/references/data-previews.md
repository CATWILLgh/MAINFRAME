# Optional data previews

Enable each browser only for an explicit operator need. Prefer safe metadata and
aggregates before raw records. Read-only does not mean cheap or non-sensitive:
logs, query text, Redis values and Kafka messages can contain credentials and
personal data. Separate metadata permission from content permission; enforce tenant,
resource and field policy before returning or caching data. Masking column names
matching 'password' is insufficient for nested JSON, arbitrary values or innocently
named sensitive fields. Prefer approved field projections and omit unknown content.

Use least-privileged connections/credentials and explicit query/command allowlists.
No arbitrary SQL, Redis commands or Kafka admin operations. Bound server work as
well as response size: deadlines, rows, bytes, objects, partitions, scans and
concurrency. Post-fetch truncation cannot undo a huge allocation or expensive
query. Cancel actual operations and distinguish denied, empty, unsupported and
failed results. Identify production/shared/test targets explicitly; a tunnel or
local address never establishes disposable test data.

## PostgreSQL

Use approved relations and fields, enforce tenant predicates and preserve applicable
row-level security. Do not browse through the application's owner/superuser account
assuming UI authorization replaces database restrictions. Read-only transactions
alone do not prevent expensive functions or disclosure through views.

Resolve relations through approved catalogs and quote schema and table identifiers
independently using the driver's identifier facility. Parameterize values; a
catalog-derived schema still needs correct quoting. Set statement/lock timeouts
and transaction cleanup. LIMIT bounds returned rows, not necessarily scans, sorts,
large field materialization or expensive views. Choose predictable pagination and
projection with byte bounds. Explain snapshot/concurrent-change behavior rather
than imply a stable full export. Query activity text may embed sensitive literals;
show safe metadata unless detailed access and redaction are established.

## Redis

Use cursor SCAN rather than KEYS for iteration, with a total time/iteration budget.
COUNT is a work hint, not a strict result bound; pages may be empty before cursor
zero and duplicates may occur. Preserve cursor semantics, deduplicate where needed,
and report partial results honestly. Use supported cluster-aware iteration when
required; one node's cursor is not the whole cluster.

Preview approved key namespaces and types. Avoid unbounded GET/HGETALL/SMEMBERS
on unknown values; use bounded range/scan operations and response limits. Size
prechecks race with writes, so do not rely on them alone. Keys, session values and
slowlog arguments can themselves be sensitive. Do not turn expired-between-reads
or type-changed keys into generic corruption claims.

## Kafka

Use dedicated authorized read credentials and bounded partition/range selection.
Never join the production consumer group, commit its offsets or alter its position
for a preview. A separate reader without group commits still consumes broker,
network and memory capacity. Bound partitions, messages, bytes, fetch wait and
concurrency; close readers and propagate cancellation. Consumer fetch byte settings
can allow an oversized first batch for progress; verify library/broker limits and
bound decoding/output rather than treating fetch.max.bytes as a hard memory cap.

Show topic/partition/offset and safe timestamps. Retention, compaction and gaps
mean offsets are not a count of available messages. There is no global ordering
across partitions; sorting a sampled tail by timestamp does not create one.
Decode only approved formats with size limits and redact before output. A preview
must not execute deserialized content or expose entire business payloads by default.

## Primary references

Reviewed 2026-10-04:

- [PostgreSQL timeouts and read-only defaults](https://www.postgresql.org/docs/current/runtime-config-client.html)
- [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Redis SCAN guarantees and limitations](https://redis.io/docs/latest/commands/scan/)
- [Kafka consumer configuration](https://kafka.apache.org/43/configuration/consumer-configs/)

Check actual library/version behavior before selecting cancellation, iteration or
consumer APIs. The method does not require deploying any of these services.
