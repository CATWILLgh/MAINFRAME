# Multitenancy patterns

Three shapes: separate schema per tenant, shared schema with discriminator column, PostgreSQL Row Level Security. For most enterprise backends — RLS (defense-in-depth: DB enforces even if app forgets a `.filter()`).

## PostgreSQL RLS

- Per PostgreSQL docs: «Tables can have row security policies that restrict, on a per-user basis, which rows can be returned by normal queries or inserted, updated, or deleted by data modification commands.»
- Activate per table: `ALTER TABLE <t> ENABLE ROW LEVEL SECURITY; ALTER TABLE <t> FORCE ROW LEVEL SECURITY;`.
- Policy reads tenant context from session GUC: `CREATE POLICY tenant_isolation ON <t> USING (organization_id = current_setting('app.current_tenant')::bigint);`.

## CRITICAL caveat — referential integrity bypasses RLS

Per PostgreSQL docs: «Referential integrity checks, such as unique or primary key constraints and foreign key references, always bypass row security to ensure that data integrity is maintained.»

Practical consequences:
- A `UNIQUE` column visible to one tenant prevents another from inserting the same value (information leak).
- FK validation can confirm row existence across tenant boundaries.
- Mitigation: include `organization_id` in composite UNIQUE indices; review FK relationships for cross-tenant exposure.

## Tenant context propagation

| Mode | Mechanism |
|---|---|
| **Sync Flask** | `flask.g.tenant_id` set in `before_request` from JWT; emit `SET LOCAL app.current_tenant = ...` in DB session opener |
| **Sync Django** | Middleware sets `request.tenant_id`; thread-local or DB session GUC for query-time |
| **Async FastAPI / Starlette** | `contextvars.ContextVar("tenant_id")` set in middleware; survives `await` boundaries (thread-locals do NOT) |

Anti-pattern in async: thread-local (`threading.local()`) for tenant — gets lost across `await`. Always use `ContextVar` for async stacks.

## Tenant identity from JWT, never from request body

- JWT claim (`org_id`, `tenant_id`) is the authoritative source — set on auth, verified on every protected request.
- Endpoints that accept tenant scope in the body are a known privilege-escalation pattern. Reject at the schema level: do not declare `organization_id` as an `*In` field.
- `getattr(obj, "organization_id", 0)` fallback to 0 → leaks all-tenants global namespace. Forbid this access pattern.

## Background workers + multitenancy

- Celery / ARQ tasks do NOT carry HTTP request context. Tenant must be passed as a task argument, set on the worker's DB session at the start of the task.
- Add a worker-level base task class that sets and clears tenant context around `run()`.

## Sources

- PostgreSQL Row Security — https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- Python contextvars — https://docs.python.org/3/library/contextvars.html
