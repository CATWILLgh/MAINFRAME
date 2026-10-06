# Testing

Use `mainframe-testing` for red/green/refactor, the lightweight local PostgreSQL boundary, and CI ownership. Apply the stack-specific details below within that boundary; real service-backed checks beyond local PostgreSQL run in CI by default.

Use the project's native Go commands, fixtures, and dependency boundaries.
Choose the smallest faithful proof: pure rules at package level, HTTP contracts
through the real handler/middleware, provider behavior through a bounded fake
transport, and locking, constraints, migrations, sessions, or SQL through the
actual database engine.

Run focused packages first. Add `-race` when the changed code or invariant
involves goroutines, shared state, connection ownership, cancellation, or
concurrent requests. The race detector finds data races; it does not prove
transaction isolation, deadlock freedom, idempotency, ordering, or business
correctness. Run the project's configured `go vet`, static analysis, and broader
suite only as justified by the changed surface.

Make concurrent tests deterministic with barriers, channels, database locks, or
observable state instead of sleeps. Assert the final invariant and resource
release, not only that calls returned. Use isolated schemas or databases for
engine-specific tests, verify the endpoint is truly disposable/local under the
effective project policy, and clean up even after failure. Avoid `t.Parallel`
when fixtures share process globals, ports, clocks, schemas, or pool limits.

With `httptest`, exercise authentication, authorization, middleware, invalid
input, safe output projection, headers, and status mapping. With fake HTTP
providers, assert request method/path/query/body and cover malformed responses,
pagination traps, rate limits, timeouts, and ambiguous mutation outcomes without
printing credentials.

Name the evidence boundary accurately. Recreating a store, handler, or session
manager is not an actual process restart; abandoning a transaction is not a
process kill; a fake provider is not live compatibility; a health response is
not end-to-end readiness. Report what ran and the material boundary still
unverified.
