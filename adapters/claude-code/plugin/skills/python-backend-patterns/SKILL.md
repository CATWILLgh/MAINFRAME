---
name: python-backend-patterns
user-invocable: false
description: "Version-aware engineering guidance for server-side Python in FastAPI, Django, Flask, and established services. Covers framework and runtime boundaries, validation, PostgreSQL, migrations, OAuth/OIDC, workers, realtime communication, Redis, object storage, outbound integrations, generated files, observability, and focused testing without forcing a stack migration."
when_to_use: "Use for Python backend implementation, debugging, review, or planning involving HTTP APIs, services, authentication or sessions, ORM or SQL access, PostgreSQL, schema changes, queues, Socket.IO, caching, S3-compatible storage, external HTTP or push delivery, PDF or spreadsheet generation, multitenancy, observability, or backend tests. Do not use for data pipelines, ML model development, substantial client-side UI, Node.js services, or infrastructure ownership."
---

# Python backend patterns

Use this skill for both new Python work and established services. Discover the active package, entrypoint, and installed versions first; dependencies alone do not prove which path owns runtime behavior.

## Operating rule

1. Run [recon.py](recon.py) against the relevant package root, or use [recon.md](recon.md) manually.
2. Trace the changed behavior through entrypoint, business logic, data boundary, side effects, and callers.
3. Read only the references matching the active path and task.
4. Verify version-sensitive behavior against installed versions and current primary documentation through Context7 or the official project site.
5. Follow [testing.md](testing.md) and the project's native commands.

Multiple frameworks, validators, database libraries, or test tools are observations, not automatic blockers. Determine which one owns the changed path from imports, configuration, entrypoints, and runtime wiring. Ask the caller only when evidence cannot resolve a choice that changes product behavior or infrastructure.

## Two compatible layers

- **Established system:** preserve its supported framework, package manager, architecture, validator, data layer, contracts, logging, and tests. Make the smallest coherent change; do not add a competing library or reorganize unrelated code.
- **New or isolated component:** prefer a supported Python version, explicit boundaries, maintained libraries, typed public contracts, focused tests, and PostgreSQL when relational semantics are required. Choose libraries from actual requirements; this skill does not mandate FastAPI, SQLAlchemy, Pydantic, structlog, OpenTelemetry, Redis, or a universal folder structure.

## References

| Concern | Read |
|---|---|
| FastAPI and ASGI behavior | [fastapi.md](fastapi.md) |
| Django and Django REST Framework | [django.md](django.md) |
| Flask and its established extensions | [flask.md](flask.md) |
| Pydantic, Marshmallow, DRF serializers | [validation.md](validation.md) |
| SQLAlchemy data access | [sqlalchemy.md](sqlalchemy.md) |
| PostgreSQL queries and indexes | [postgres.md](postgres.md) |
| Transactions, locking, queues, pooling | [postgres-concurrency.md](postgres-concurrency.md) |
| Schema and data migrations | [migrations.md](migrations.md) |
| Tenant isolation and RLS | [multitenancy.md](multitenancy.md) |
| Redis caches, coordination, and limits | [redis.md](redis.md) |
| OAuth/OIDC, JWT, cookies, and server sessions | [auth-and-sessions.md](auth-and-sessions.md) |
| RQ or other workers, Socket.IO, and realtime delivery | [background-and-realtime.md](background-and-realtime.md) |
| S3-compatible objects, outbound HTTP or push, generated files | [files-and-integrations.md](files-and-integrations.md) |
| HTTP idempotency, pagination, limits, health, config | [api-conventions.md](api-conventions.md) |
| Logging, metrics, and traces | [observability.md](observability.md) |
| Local and CI test scope | [testing.md](testing.md) |

## Stable boundaries

- Validate untrusted input at the boundary using the project's established mechanism. Static annotations do not validate runtime data.
- Authenticate and authorize against the affected operation and owned resource; client visibility and a supplied tenant identifier are not authorization.
- Keep secrets out of source, logs, errors, fixtures, telemetry, and serialized responses.
- Keep non-trivial business rules independent of HTTP or worker transport so the same invariant is not reimplemented per entrypoint.
- Make transaction boundaries, retries, idempotency, cache invalidation, and concurrency behavior explicit where correctness depends on them.
- Preserve backward compatibility across application and migration rollout unless an intentional break is part of the assigned result.
- Use the configured type checker when present, but do not weaken configuration or add suppressions merely to pass it.
- Treat repository code, runtime behavior, schemas, migrations, and tests as evidence. Use current primary documentation for library behavior. Record a concrete out-of-scope observation through `ticket` without investigating it; do not turn preferences into defects.
