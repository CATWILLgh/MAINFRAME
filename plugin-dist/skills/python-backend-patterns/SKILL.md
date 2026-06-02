---
name: python-backend-patterns
user-invocable: false
disable-model-invocation: true
description: "Stack-adaptive Python backend patterns — recon-driven dispatch across FastAPI / Django / Flask with cross-cutting concerns (SQLAlchemy 2.0 + Pydantic 2 / Marshmallow / DRF, multitenancy via PostgreSQL RLS, structlog + OpenTelemetry observability, pytest + testcontainers testing, typed exceptions, eager loading discipline). Loaded by `python-backend-engineer` agent only; closed to main-context auto-invocation."
when_to_use: "A Python backend task is in flight inside the `python-backend-engineer` sub-agent — implementing HTTP endpoints, ORM models, auth/JWT, background workers, observability, multitenancy. Triggered via agent frontmatter `skills:` preload, not by direct user invocation. Out of scope: data pipelines (`data-engineer` role), full DevOps ownership, ML serving."
---

# Python backend patterns — stack-adaptive entry

Preloaded into the `python-backend-engineer` sub-agent. Provides a dispatch table from project recon to per-stack pattern files, plus universal principles applied across all stacks.

## How to use

1. **Recon first.** Run the script [recon.py](recon.py) — `python3 ~/.claude/skills/mainframe/skills/python-backend-patterns/recon.py [project_root]` — for deterministic parse of `pyproject.toml` + `requirements.txt`. Manual fallback per [recon.md](recon.md) when script unavailable or project is `Pipfile` / `setup.py`-only.
2. **Apply universal principles** (below) — they hold regardless of stack.
3. **Dispatch by recon outcome** — read the relevant supporting file(s) from the table below. Do NOT pre-read files irrelevant to the recon outcome (token discipline).
4. **For endpoint-specific situational concerns** (idempotency, pagination, rate limiting, health probes, config-from-env) — consult [api-conventions.md](api-conventions.md) when the concern is in scope.
5. **Test** per [testing.md](testing.md) — the 4-scenario contract for every endpoint is non-negotiable.

## Dispatch table

| Recon outcome | Read this |
|---|---|
| `framework: fastapi` | [fastapi.md](fastapi.md) |
| `framework: django` | [django.md](django.md) |
| `framework: flask` | [flask.md](flask.md) |
| `framework: niche-name` | [fastapi.md](fastapi.md) as closest analogue + flag mismatch |
| `orm: sqlalchemy-2` (Flask / FastAPI) | [sqlalchemy.md](sqlalchemy.md) |
| `orm: django` | Django ORM specifics inside [django.md](django.md) |
| `validation: pydantic-2` OR `marshmallow` OR `drf` | [validation.md](validation.md) |
| `multitenancy: rls` OR `app-filter` | [multitenancy.md](multitenancy.md) |
| `observability: structlog+otel` OR `stdlib-logging` | [observability.md](observability.md) |
| Any testing task | [testing.md](testing.md) |
| Any migration / schema-change task | [migrations.md](migrations.md) |
| Idempotency / pagination / rate limiting / health probes / config-from-env | [api-conventions.md](api-conventions.md) |

## Universal principles (apply across stacks)

These hold regardless of framework / ORM / validation choice. Cross-reference the umbrella CLAUDE.md rules (CQS, debug residue, marker bans, etc.) — they apply here too, not duplicated.

### The server is canonical — authority, state, computed values

Validation of inbound request data at the trust boundary (request → handler) is mandatory; that rule lives in the umbrella `CLAUDE.md` Engineering practices ("Trust framework and type-system guarantees": "data at system boundaries… is untrusted and must be validated"). Apply it. This bullet adds the **authority half** beyond schema validation:

- **Authorization on every protected endpoint, server-checked** against actual tenant + role from JWT. Per OWASP Authorization Cheat Sheet: "Access control checks must be performed server-side, at the gateway, or using serverless function… client-side checks may be permissible for improving the user experience, they should never be the decisive factor". Decorators / route-level auth alone are not enough for high-stakes operations — re-check ownership in the service layer.
- **Business state transitions controlled by the server.** Status flow (e.g. `draft → submitted → approved`) is a whitelist defined and enforced in the service layer. Reject unauthorised transitions there, not at the route.
- **Computed and derived values come from the server.** Totals, percentages, aggregate counts, computed prices, derived statuses — recompute server-side. Never accept these as input fields even if the client computed them.
- **Related-resource IDs are ownership-verified server-side.** When a request body contains `machine_id`, `job_id`, etc., load the row server-side and check ownership against the JWT tenant before any operation. The client cannot be trusted to send only IDs it owns.
- **Client-side validation is a UX accelerator only.** Per OWASP Input Validation Cheat Sheet: "Implementing both client-side JavaScript-based validation for UX and server-side validation for security is the recommended approach". Per MDN: "Never trust data passed to your server from the client. Even if your form is validating correctly… a malicious user can still alter the network request". Reproduce all schema and business checks server-side regardless of what the client form did.

### Layer split

`api` (HTTP orchestration) → `services` (business logic) → `models` (data structure) → `schemas` (validation boundaries) → `utils` (pure helpers). Names differ per framework (FastAPI: `routers`, Django: `views.py`/`viewsets.py`, Flask: `blueprints`), shape is the same. Business logic NEVER lives in HTTP handlers.

### Tenant identity is JWT-sourced

`organization_id` / `tenant_id` comes from the JWT claim, set on every protected request. Endpoints that accept it from the request body are a privilege-escalation pattern — reject at the schema level. Fallback `getattr(obj, "organization_id", 0)` is forbidden. See [multitenancy.md](multitenancy.md) for propagation in async vs sync.

### Audit trail on state-changing operations

Every CRUD + status-transition on a business entity emits an audit event with `organization_id`, `actor_user_id`, `action`, `entity_type`, `entity_id`, `new_values` (omit secrets). Append-only store, never updated. Use a structured `log_audit_event(...)` helper, not ad-hoc log lines.

### Structured logging + tracing

`structlog.get_logger()` per module; bind request-scoped context once per request (request_id, user_id, org_id). OpenTelemetry auto-instrumentation for the framework + ORM. Logs carry `trace_id` so backend joins logs + traces. Never log raw request bodies — whitelist fields. See [observability.md](observability.md).

### Typed exception handling

`except SQLAlchemyError`, `except IntegrityError` — never bare `except` or `except Exception`. `IntegrityError.pgcode` discriminates unique (`23505`) / FK (`23503`) / CHECK (`23514`) for accurate user-facing errors (409 vs 400 vs 422). Bare `except: pass` is a banned anti-pattern (see umbrella CLAUDE.md). Domain exceptions translated to HTTP at the handler boundary, never raw ORM errors leaked.

### Eager loading discipline

The N+1 query problem is the prime backend regression. List endpoints MUST pre-load relationships used by the response. SQLAlchemy: `joinedload` (many-to-one) vs `selectinload` (collections) — see [sqlalchemy.md](sqlalchemy.md). Django ORM: `select_related` vs `prefetch_related` — see [django.md](django.md). Anti-pattern in both: lazy access inside the response serialiser.

### Response envelope unification

Paginated list responses: one consistent envelope shape across the API surface, e.g. `{"items": [...], "total": N, "page": N, "per_page": N, "has_more": bool}`. NOT a different shape per resource (`{"jobs": [...]}` vs `{"users": [...]}`). Backward-compat aliases acceptable only during a documented migration.

### HTTP status codes

`POST` create → `201 Created`. `POST` state-transition → `200 OK`. `DELETE` → `204 No Content`. `PUT` / `PATCH` → `200 OK` with body. `409 Conflict` for unique violations (idempotency, race losers). `422 Unprocessable Entity` for business-rule violation (semantically valid input, but rule says no).

### Bulk endpoints have hard limits

Any endpoint that accepts an array of IDs / objects MUST cap input size — `if len(items) > N: raise ValidationError(...)`. Typical N: 50-100 depending on the operation's per-item cost. Unbounded bulk endpoints are DoS vectors.

### Aggregates live in SQL

`func.sum`, `func.count`, `func.avg`, `case()` — let the database aggregate. Python loops over fetched result sets are an anti-pattern except when the calculation requires Python-only context (e.g. `datetime.now()` for live active-time).

## Out of scope

- Data pipelines (ETL, pandas, polars, dask) — separate `data-engineer` role.
- Full ML serving stacks — separate `ml-engineer` role.
- Infrastructure ownership (Kubernetes operators, full-stack IaC) — separate `devops-engineer` role. Backend engineer reads `Dockerfile` and CI config, doesn't own them.

## Sources

Per-supporting-file authoritative URLs are at the bottom of each file. Umbrella enterprise pattern references that informed this skill:

- JetBrains Python Developers Survey 2024 — framework adoption data informing the FastAPI / Django / Flask coverage decision.
- SQLAlchemy 2.0 ORM Querying Guide — https://docs.sqlalchemy.org/en/20/orm/queryguide/
- Pydantic 2 docs — https://docs.pydantic.dev/latest/
- PostgreSQL Row Security — https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- OpenTelemetry Python — https://opentelemetry.io/docs/languages/python/
- OWASP Input Validation Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- OWASP Authorization Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- MDN Form Validation — https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms/Form_validation
