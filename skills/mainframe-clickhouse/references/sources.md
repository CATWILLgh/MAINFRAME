# Official source map

Use the applicable official page for the target version and deployment mode.
This skill was researched on 2026-10-02; documentation and defaults can change.
Installed version, engine, grants, configuration and observed behavior control
the active operation. Do not upgrade or enable a feature merely to fit an example.

| Decision | Primary source |
| --- | --- |
| Read-only semantics, grants and settings constraints | [Query permissions](https://clickhouse.com/docs/operations/settings/permissions-for-queries) and its linked settings/constraints references |
| Query budgets, overflow and distributed limits | [Query complexity](https://clickhouse.com/docs/operations/settings/query-complexity) |
| Client response completeness and disconnection | [HTTP interface](https://clickhouse.com/docs/interfaces/http) |
| Non-executing plan inspection | [EXPLAIN](https://clickhouse.com/docs/sql-reference/statements/explain) |
| Replacement, versioning and query-time correctness | [ReplacingMergeTree](https://clickhouse.com/docs/engines/table-engines/mergetree-family/replacingmergetree) |
| Batching, asynchronous acknowledgments and retry deduplication | [Insert strategy](https://clickhouse.com/docs/best-practices/selecting-an-insert-strategy) and its linked retry/deduplication reference |
| Buffered shard delivery | [Distributed engine](https://clickhouse.com/docs/engines/table-engines/special/distributed) |
| Mutation cost, synchronization and deletion semantics | [ALTER DELETE](https://clickhouse.com/docs/sql-reference/statements/alter/delete), [DELETE](https://clickhouse.com/docs/sql-reference/statements/delete) |
| Source correction and materialized dependencies | [Incremental materialized views](https://clickhouse.com/docs/materialized-view/incremental-materialized-view) |
| Cluster DDL propagation | [Distributed DDL](https://clickhouse.com/docs/sql-reference/distributed-ddl) |
| Cancellation and lack of mutation rollback | [KILL](https://clickhouse.com/docs/sql-reference/statements/kill) |
| Forced merges versus query FINAL | [Avoid OPTIMIZE FINAL](https://clickhouse.com/docs/best-practices/avoid-optimize-final) |
| Backup completion and verified restoration | [Backup and restore](https://clickhouse.com/docs/operations/backup) |

Check unsupported syntax/settings against the installed release before choosing
an alternative. New update methods, asynchronous deduplication and permissions
can differ across releases. An example cluster name, credential, numeric budget,
or database is never a safe default for a real target.
