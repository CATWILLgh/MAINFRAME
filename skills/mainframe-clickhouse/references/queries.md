# Safe queries and useful results

## Bound cost before execution

Choose only needed columns, an explicit time/key range, and a limited result.
Check the sorting/partition keys and relevant engine using bounded metadata.
For an unfamiliar plan, use a supported non-executing `EXPLAIN` mode to assess
index/partition pruning and joins before reading the data. Check mode semantics;
an execution/profiling mode is a workload, not a free preview. Planning can still
perform metadata or external-source work, so keep it within the established scope.

`LIMIT` constrains returned rows, not necessarily scanned rows or aggregation,
sort, join, or `FINAL` work. Avoid unrestricted counts, broad text searches,
`SELECT *`, and whole-history aggregates as exploratory defaults. A bounded
representative interval is preferable to a succession of speculative heavy
queries. Do not silently replace an exact answer with a sample or approximate
aggregate; label approximation and confirm it meets the requested result.

Use the effective profile or permitted query settings to bound execution time,
read rows/bytes, memory, result size, and concurrency as relevant. Set values
from the target's approved workload budget, not a universal copied example.
Many maximum settings use zero for unlimited. Distributed limits commonly apply
per server; verify leaf limits and fan-out rather than calling a per-node cap a
cluster-wide budget. Memory spill can shift pressure to disk.

Prefer applicable overflow modes that throw. `break` and truncated responses can
produce partial answers; an HTTP success or plausible aggregate does not prove
completeness. Check driver errors and response completion. Server time limits
are checked at processing boundaries and can overshoot; combine them with a
client deadline and a scoped cancellation plan. A disconnected client is not
proof that server work stopped. Use a non-secret query ID to track the submitted
request; do not cancel someone else's query or run blanket cancellation.

For distributed reads, inspect completeness-affecting settings such as
`skip_unavailable_shards`. Missing shards can yield plausible incomplete answers;
do not enable silent skipping to make a failed report look successful.

## Verify index benefit

Derive sorting/primary-key order, skipping-index or projection candidates from
actual application filters, ordering and data distribution. Compare existing
definitions first; adding an index to every filtered column is not a strategy.
Use the supported `EXPLAIN` index/projection output to check parts/granules
pruned. Follow the target version's inspection settings; caches and newer
read-time skip-index evaluation can change what a planning report shows.

Compare the actual query and correct application result before/after under
representative parameters, data, concurrency and cache conditions. Use bounded
existing telemetry for elapsed time, read rows/bytes and memory; pair read
benefit with index/projection storage and insert/merge cost. Pruning or an index
name in a plan alone does not establish improvement. Retain a real-engine
correctness and cost/time check; for a performance fix, show it rejects the known
defect. Costly workloads belong on the existing CI route. Reuse the shared
[performance method](../../mainframe-testing/references/performance.md) for
workload and acceptance design. Use [writes and schema](writes.md) to verify
coverage of existing data and rollout completion; definition existence alone
does not prove either. Do not apply PostgreSQL catalog flags or B-tree rules.

## Preserve correctness and confidentiality

Inspect the engine's semantics. A ClickHouse primary key is not a uniqueness
constraint. `ReplacingMergeTree` replacement depends on the sorting key and
background merges; duplicates may remain. Choose the query's required version,
deletion and aggregation semantics explicitly. `SELECT ... FINAL` can be needed
for correctness and should be cost-bounded; do not remove it just to get a faster
but wrong answer. It differs from the mutating `OPTIMIZE ... FINAL` operation.

Trace view and Distributed-table dependencies when they change access or load.
`remote`, `clusterAllReplicas`, `url`, `s3`, `file`, dictionaries, and other
external reads can expand destinations, fan-out, or data exposure. `SELECT` is
not permission to access every referenced system. Do not embed credentials in
SQL, URLs, or diagnostic output.

For incident telemetry, select only necessary status, counters and timestamps
from the relevant system tables, scoped to the object, query ID and interval.
Avoid raw query text, exception dumps, `SHOW CREATE` of credential-bearing
objects, and whole configuration or query-log exports. If query text is needed,
sanitize it before retaining or returning it. Logs may lag; absence is not proof
of failure, and flushing logs is an operation, not a default diagnostic step.

Sources: [Complexity limits](https://clickhouse.com/docs/operations/settings/query-complexity),
[EXPLAIN](https://clickhouse.com/docs/sql-reference/statements/explain),
[ReplacingMergeTree](https://clickhouse.com/docs/engines/table-engines/mergetree-family/replacingmergetree),
[Distributed engine](https://clickhouse.com/docs/engines/table-engines/special/distributed),
[HTTP response and cancellation semantics](https://clickhouse.com/docs/interfaces/http).
