# Performance and database regression checks

Use this layer when changing a critical path's work, a shared queue or
connection pool, database access or contention, or making a speed or resource
claim. Start with the user or system result that must stay usable. Map it to
the owning check, workload, and acceptance condition in the project's
[verification map](strategy.md#keep-one-project-verification-map).

## Choose the workload and what passes

Define the measured interval from the normal entrypoint to useful completion.
For asynchronous work distinguish acknowledgement, queue delay, processing, and
durable completion. Test the existing journey alongside new background or
provider work when they share capacity. Where relevant, assert admission,
durable completion, progress on the next item, and behavior under a slow or
failed dependency.

Use representative data size and skew, cache state, concurrency, and resource
limits. Match inputs, offered load, engine, and runner profile for baseline
and candidate. Keep setup and warmup outside the timed interval. Define which
baseline failures demonstrate the defect and which invalidate comparison.
Investigate a failed control before repeating an expensive run. Correct a
faulty measuring tool within scope and reconcile changed acceptance conditions
with their decision owner.

Choose an absolute or relative budget from the product requirement or a
measured baseline. Record sample size and relevant limits. For interactive
paths compare successful latency and a tail percentile the sample supports,
and count errors and timeouts separately. For a worker or queue, measure
useful completions, oldest work age or time to drain, and retries or lost work
as applicable. Pair those results with the limiting resource, such as
CPU, memory, I/O, locks, or pool occupancy. A fast rejection earns no credit
as a successful completion.

## Choose the smallest faithful check

| Risk | Evidence |
| --- | --- |
| Repeated work, queries growing with item count, or unbounded fan-out | A fast regression with a meaningful bound on calls, rows, concurrency, or allocations, plus the correct result |
| DB locks, transaction timing, pool exhaustion, or worker overlap | Correct-engine test with controlled concurrency. Hold the competing operation explicitly and assert required progress, or a bounded failure with no lost or repeated effect |
| Schema changes, index/constraint operations, or backfills | [Migration method](migrations.md), including representative upgrade, runner transaction boundaries, and application progress under overlap |
| User latency, throughput, saturation, or resource regression | A controlled before/after benchmark or CI job with an explicit pass condition. Preserve correctness, timeout and successful-completion counts |
| A claim about the deployed journey | Observe the normal user or system path in the authorized environment, including the relevant background load, role or device. Keep the preceding test evidence and name any missing acceptance |

Use the project's existing runner and workload. Keep fast deterministic checks
in the local loop. Run expensive load tests in CI or a specifically authorized
environment. A logged timing helps diagnosis. For a performance gate, make the
chosen budget or causal bound an assertion that can reject the defect.
Demonstrate that it rejects the baseline defect for a regression fix.

## Prove index usefulness and cost

Use for index design, query/index changes, or missing/unused-index claims.
Establish the index's purpose: query acceleration, an integrity constraint, or
both. Separate installed validity, applicability to the query, planner choice,
and measured benefit; none alone proves the others. Use the
[migration method](migrations.md) for build readiness and safe replacement.
For an integrity-only index, prove the intended accepted/rejected writes under
relevant concurrency and bound affected cost; read-scan use is not its purpose.

- Inspect the application's actual SQL, parameter types and representative
  values, role/schema, and prepared-query behavior. Include filters, joins,
  tenant scope, ordering and pagination. Compare existing index definitions and
  current data statistics before choosing key order, a predicate, expression,
  or included columns for the actual engine/version.
- Inspect the plan for that query through the actual client execution mode
  where relevant, including generic/custom prepared plans. Check partial-index
  predicate implication, expressions, casts, collation and operator compatibility.
  Parameters do not categorically prevent index use; a literal-only console
  query does not prove the application's parameterized query can use it.
- For claimed read acceleration, confirm the actual statement's chosen access
  path and compare query work AND useful application completion before/after
  under the workload above. Inspect rows, loops, buffers/I/O, sorting and heap
  access as relevant, across common and selective parameter values. Investigate stale
  statistics or row-estimate errors. An index scan can be slower than a table
  scan; accept a justified plan that meets the result and cost budget. Forcing
  index use is a diagnostic experiment, not acceptance evidence.
- Compare affected insert/update/delete throughput and latency, index size,
  WAL/I/O and maintenance cost where relevant. Included or frequently changed
  columns can increase storage and write work; do not judge a read improvement
  in isolation. Faster row discovery does not release transaction-held locks;
  retain the concurrent-progress check when contention is the risk.
- Preserve a regression on the real engine with representative data/statistics
  and actual query bindings. Assert correct results and the relevant time or
  work budget. For a performance fix, show it rejects the known defect, such as
  the previous query or a fixture lacking the required index. Stable plan
  properties may support the check; index existence, a scan-node name, or full-plan text equality alone
  cannot establish benefit. Keep expensive workloads on the existing CI route.

For ongoing control, reuse scoped statement/index statistics and metrics where
available. Compare deltas over an identified workload interval, accounting for
counter resets, replica routing and rare jobs. Index counters do not attribute
benefit to a particular query or equal successful query counts. Do not reset
shared statistics, install monitoring infrastructure, or delete indexes merely
to complete a check. Record the query family, actual definition/readiness,
plan evidence, read/write/resource results and regression command in the
verification map. Name missing runtime evidence rather than claiming usefulness.

PostgreSQL sources: [Index usage and statistics](https://www.postgresql.org/docs/current/indexes-examine.html),
[Multicolumn indexes](https://www.postgresql.org/docs/current/indexes-multicolumn.html),
[Partial indexes](https://www.postgresql.org/docs/current/indexes-partial.html),
[Covering indexes](https://www.postgresql.org/docs/current/indexes-index-only-scans.html),
[HOT update conditions](https://www.postgresql.org/docs/current/storage-hot.html),
[Index statistics](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-ALL-INDEXES-VIEW).
Use the matching engine's method; ClickHouse has separate
[index/pruning checks](../../mainframe-clickhouse/references/queries.md#verify-index-benefit).

## Diagnose database cost and blocking

Trace connection acquisition, each query or batch, transaction lifetime, and
resource release. Measure pool wait separately from execution, and identify
the waiter and holder before calling a timeout a lock or pool problem. Count
work across realistic small and large inputs. Inspect plan rows, loops, and
I/O where relevant. Preserve ordering, pagination, authorization, and write
semantics when replacing or batching queries.

Use engine evidence for locks, isolation, plans, and migrations. Test blocking
with distinct sessions and a barrier, then check progress, cancellation, and
connection cleanup. Where the protocol permits, release transactions and
connections before a queue, quota, or provider wait. Check lock order across
the affected paths. Verify the actual bottleneck before raising timeouts,
retries, concurrency, or pool capacity.

For PostgreSQL, use bounded `pg_stat_activity` and `pg_blocking_pids` evidence
when lock attribution matters, and existing statement statistics when
available. Choose `EXPLAIN` for the plan. `EXPLAIN ANALYZE` executes the
statement and adds measurement overhead, so prefer an isolated authorized
database for this diagnostic. Use the normal application path for acceptance
timings. Consult the documentation for the actual server version.
[Monitoring statistics](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-ACTIVITY-VIEW)
· [Blocking sessions](https://www.postgresql.org/docs/current/functions-info.html)
· [EXPLAIN](https://www.postgresql.org/docs/current/sql-explain.html)
· [Locking](https://www.postgresql.org/docs/current/explicit-locking.html)

Keep changed critical paths diagnosable through existing metrics and
[structured logs](../../mainframe-logging/SKILL.md). Emit only context that
separates the plausible causes. Aggregate timings where useful and keep raw
parameters and payloads out of telemetry.

The signal choices follow Google SRE's guidance on latency, traffic, errors,
saturation, and user-facing measurements. OpenTelemetry's database client
conventions distinguish operation duration from pool wait. Check each
convention's stability before adopting its metric names.
[Monitoring distributed systems](https://sre.google/sre-book/monitoring-distributed-systems/#the-four-golden-signals)
· [Service level objectives](https://sre.google/sre-book/service-level-objectives/)
· [Database client metrics](https://opentelemetry.io/docs/specs/semconv/db/database-metrics/)
