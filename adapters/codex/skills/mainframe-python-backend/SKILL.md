---
name: mainframe-python-backend
description: Implement, debug, review, or plan server-side Python in FastAPI, Django, Flask, and established Python services. Use for HTTP APIs, business logic, authentication, PostgreSQL, SQLAlchemy, migrations, workers, realtime behavior, caching, object storage, external integrations, generated documents, observability, and backend tests. Do not use for data pipelines, ML model development, substantial client-side UI, Node.js services, or infrastructure ownership.
---

# Python backend engineering

Discover the active package, entrypoint, and installed stack before choosing an
approach. Dependencies and repository names do not prove which framework,
database path, worker, or test setup owns runtime behavior.

## Work sequence

1. Run the [recon script](scripts/recon.py) as
   `python3 scripts/recon.py <package-root>` from this skill, or follow
   [recon.md](references/recon.md) manually.
2. Trace the changed behavior through its entrypoint, business rules, data or
   external boundary, side effects, callers, and observable output.
3. Read only the references matching the active path and changed risk.
4. Verify installed versions and version-sensitive behavior through current
   primary documentation or Context7.
5. Use the project's native commands and the smallest faithful red-to-green
   test. Read [testing.md](references/testing.md) when selecting a test level,
   changing existing tests, or separating local and CI checks.

Several frameworks, validators, database libraries, or test runners are
observations, not automatic blockers. Resolve the active owner from imports,
configuration, entrypoints, runtime wiring, and affected files. Escalate only
an unresolved choice that changes product behavior, infrastructure,
permissions, or the assigned result.

Complete the assigned behavior. Do not substitute TODOs, placeholders, skipped
or weakened tests, suppressions, or deferred in-scope work for implementation.

## Preserve or introduce deliberately

- In an established system, preserve its supported Python version, package
  manager, framework, architecture, validator, data layer, logging, contracts,
  and tests. Make the smallest coherent change; do not add a competing library
  or incidental migration.
- In a new isolated component, prefer a supported Python version, explicit
  boundaries, maintained libraries, typed public contracts, focused tests, and
  PostgreSQL when relational semantics are required. Select libraries from the
  real requirements rather than a universal preferred stack.

## Reference routing

| Changed concern | Read |
|---|---|
| FastAPI and ASGI behavior | [fastapi.md](references/fastapi.md) |
| Django and Django REST Framework | [django.md](references/django.md) |
| Flask and established extensions | [flask.md](references/flask.md) |
| Pydantic, Marshmallow, DRF serializers | [validation.md](references/validation.md) |
| SQLAlchemy data access | [sqlalchemy.md](references/sqlalchemy.md) |
| PostgreSQL queries and indexes | [postgres.md](references/postgres.md) |
| Transactions, locking, queues, pooling | [postgres-concurrency.md](references/postgres-concurrency.md) |
| Schema and data rollout | [migrations.md](references/migrations.md) |
| Tenant isolation and RLS | [multitenancy.md](references/multitenancy.md) |
| Redis caches, coordination, and limits | [redis.md](references/redis.md) |
| OAuth/OIDC, JWT, cookies, server sessions | [auth-and-sessions.md](references/auth-and-sessions.md) |
| Workers, Socket.IO, realtime delivery | [background-and-realtime.md](references/background-and-realtime.md) |
| Objects, outbound calls, generated files | [files-and-integrations.md](references/files-and-integrations.md) |
| HTTP idempotency, pagination, health, config | [api-conventions.md](references/api-conventions.md) |
| Logging, metrics, and traces | [observability.md](references/observability.md) |
| Test scope, cost, and local/CI split | [testing.md](references/testing.md) |

## Stable boundaries

- Validate untrusted input at the actual boundary with the established
  mechanism; static annotations do not validate runtime data.
- Authenticate and authorize the concrete operation and owned resource
  server-side. A supplied tenant identifier is input, not proof of access.
- Keep secrets out of source, logs, errors, fixtures, telemetry, and serialized
  responses.
- Keep non-trivial business rules independent of HTTP or worker transport.
- Make transactions, retries, idempotency, cache invalidation, and concurrency
  explicit where correctness depends on them.
- Preserve application and migration rollout compatibility unless an
  intentional break belongs to the assigned result.
- Use the configured type checker when present, without weakening it or adding
  suppressions merely to pass.
- Treat repository code, runtime behavior, schemas, migrations, and tests as
  local evidence; use current owning documentation for external behavior.
- Record a concrete out-of-scope problem through `mainframe-ticket` without
  investigating it. Do not turn preferences into defects.
