# Audit dimensions

Five independent dimensions, one parallel subagent each. The categories below are
stack-agnostic — apply them through whatever stack the target uses. Treat the list as the
floor, not the ceiling: report anything serious that does not fit a category.

## Security & resilience

- Injection (unparameterized queries, unsafe interpolation); unescaped/unsanitized output.
- Authn/authz gaps: unprotected endpoints, trusting client-supplied identity or tenant.
- Secrets in code or version control; weak crypto; hardcoded credentials.
- Missing input validation at system boundaries.
- Swallowed errors (empty or overly broad catch); internal details leaked to clients.

## Architecture & clean code

- Oversized files or mixed responsibilities; layering violations; circular dependencies.
- DRY/SOLID violations; tight coupling without abstractions.
- Dead code; uninformative naming; magic values without named constants.
- Leftover suppression or placeholder markers (see the `no-suppression-markers` skill).

## Performance & data

- Repeated per-item queries (N+1); missing pagination on list endpoints.
- Missing indexes on frequent filters/joins; heavy aggregation in the wrong layer.
- Missing caching for hot reads; unbounded in-memory growth.
- Schema: imprecise types, missing constraints or defaults where the domain requires them.

## Business logic & API

- Race conditions; unprotected business invariants; transactional integrity gaps.
- Missing idempotency (retried writes create duplicates).
- Inconsistent API contracts: status codes, error shape, pagination, response envelope, versioning.

## Testing & observability

- Coverage gaps on critical paths; low-quality tests (no assertions, happy-path only).
- Flaky tests (time / order / external dependencies); non-isolated fixtures.
- Logging, metrics, or correlation-id gaps; sensitive data not masked in logs.
