# Tenant isolation

Preserve the project's chosen isolation model: separate database, separate schema, shared schema with tenant predicates, or PostgreSQL Row Level Security. Do not introduce RLS or change the tenant key as an incidental refactor.

## Request and task identity

- Derive the effective tenant from authenticated server-side context. A body, query, or path tenant identifier may select a resource but cannot authorize it.
- Verify related resource ownership inside the transaction that performs the operation.
- Background jobs have no HTTP context. Put the authenticated tenant identity into the trusted job envelope and establish database context before accessing tenant data.
- In asynchronous code, use request or task context designed to cross `await` boundaries, such as `ContextVar`; plain thread-local state is not coroutine-local.

## PostgreSQL RLS

- Inspect `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, policy roles, owner and bypass behavior, and the exact session-setting lifetime.
- Prefer transaction-local tenant settings when pooled connections are reused.
- Test permitted reads and writes plus cross-tenant rejection against real PostgreSQL.
- PostgreSQL referential-integrity checks bypass row security. Review unique and foreign-key design for cross-tenant information leaks; composite tenant-aware constraints may be required.

## Application predicates

When isolation relies on application filters, centralize the tenant-scoped query entrypoint and test that direct lookup, relationship traversal, bulk operations, exports, and workers cannot omit it. Avoid fallback tenant values that broaden scope.

## Sources

- PostgreSQL row security — https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- Python context variables — https://docs.python.org/3/library/contextvars.html
