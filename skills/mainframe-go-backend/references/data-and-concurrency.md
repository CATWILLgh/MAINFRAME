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

Treat context cancellation, serialization conflicts, deadlocks, and stale
versions as defined outcomes. Retry only the intended transaction scope with a
bounded termination rule. Use `errors.Is` with the selected database package's
documented sentinel errors rather than comparing error text.

Apply schema changes through the project's ordered migration owner. Consider
existing data, defaults, backfill size, table rewrites, index/constraint locks,
concurrent application versions, and forward recovery. Serialize multiple
processes applying migrations when the deployment can start them together.
Never edit already-applied history casually.

Database collation and Unicode behavior are part of correctness. Verify
case-insensitive or normalized uniqueness with the actual engine and locale
instead of assuming a lowercase expression covers every script.
