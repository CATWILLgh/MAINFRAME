# Data and concurrency

Use the project's concrete database API and engine semantics. Trace query,
transaction and connection ownership, constraints, isolation, lock order, pool
limits, cancellation, callers, and externally visible outcome. Close rows and
release transactions/connections on every path; check iteration errors after
reading rows.

Keep related state changes and audit/history records in one transaction when
they describe one outcome. Use constraints, ordered row locks, compare-and-set
updates, or another engine-backed mechanism for invariants exposed to concurrent
writers. Application prechecks alone may race. Choose lock strength deliberately
and keep a stable lock order across code paths.

Do not hold a transaction, row lock, or pooled connection across slow external
I/O unless the established protocol requires it and the capacity effect is
explicit. Count every simultaneously retained pool and dedicated connection;
prove progress at minimum supported capacity. A second connection can prevent
self-deadlock, but it also changes the resource bound and atomicity model.

When background writes and a user request contend, identify the lock holder,
waiting query, and time spent waiting. Reproduce overlap with the actual
engine. Verify that the request can progress at the intended capacity or
returns its defined bounded failure without losing or duplicating work.

Treat context cancellation, serialization conflicts, deadlocks, and stale
versions as defined outcomes. Retry only the intended transaction scope with a
bounded termination rule. Use `errors.Is` with the selected database package's
documented sentinel errors rather than comparing error text.

For query optimization or index design/usefulness, use the shared
[index checks](../../mainframe-testing/references/performance.md#prove-index-usefulness-and-cost).
Verify the SQL and bindings emitted by the actual Go client, not a simplified
console query; keep read benefit, write cost and concurrent progress in scope.

For schema, migration, index, constraint, or backfill changes, use the shared
[migration method](../../mainframe-testing/references/migrations.md). Keep the
project's existing migration owner and runner; inspect its Go transaction and
connection handling rather than inferring them from a migration filename.

Database collation and Unicode behavior are part of correctness. Verify
case-insensitive or normalized uniqueness with the actual engine and locale
instead of assuming a lowercase expression covers every script.
