---
name: mainframe-python-backend
description: Develop, debug, review, or test server-side Python in FastAPI, Django, Flask, and other established services. Use proactively for backend APIs, business rules, persistence, workers, realtime behavior, server integrations, and focused backend tests. Do not use for data or ML pipelines, substantial client-only UI, Node.js services, or infrastructure ownership.
---

# Python backend engineering

Apply this method whenever the active work matches the description, whether you are the primary implementer, a delegated engineer, or a reviewer. Follow the scope and authority supplied through the current execution path; this skill does not expand either.

## Establish the active server boundary

Identify the nearest Python package that owns the affected behavior. Run the bounded [recon script](scripts/recon.py) against that explicit package root, or follow [manual reconnaissance](references/recon.md). Treat the report as routing evidence, not as a decision engine: declared dependencies, filenames, and repository names do not prove the active runtime path.

Trace the requested behavior through its real entrypoint, runtime validation, business rules, data or external boundary, side effects, callers, and observable output. Inspect the effective project instructions and use only the infrastructure allowed by the project layer.

Several frameworks, validators, ORMs, workers, or test runners may legitimately coexist. Resolve ownership from imports, registration, configuration, entrypoints, runtime wiring, and affected files. Surface a decision only when evidence cannot resolve a product, business, data, infrastructure, permission, or authority choice with material consequences.

## Preserve the established system

Preserve the active interpreter support, packaging tool, framework, WSGI or ASGI boundary, sync or async model, architecture, validation, authentication, persistence, contracts, observability, and testing conventions unless changing one is part of the assigned result. Do not introduce a competing library, broad typing migration, new service, or infrastructure dependency for convenience.

For a genuinely new isolated component, derive the stack from its requirements, supported runtime, operational environment, and project decisions. Do not impose a universal framework, ORM, database, queue, test runner, or deployment model.

Verify installed versions before relying on version-sensitive behavior. Prefer the owning project's current primary documentation. An available documentation service may locate that corpus, but repository code and runtime evidence remain authoritative for project-owned behavior.

## Load only the relevant detail

| Changed concern | Read |
|---|---|
| Package root, interpreter, packaging, imports, WSGI/ASGI, typing, or generated ownership | [runtime and packaging](references/runtime-and-packaging.md) |
| FastAPI or Starlette routing, dependencies, lifespan, or async behavior | [FastAPI](references/fastapi.md) |
| Django, Django REST Framework, apps, middleware, ORM, or migrations | [Django](references/django.md) |
| Flask, blueprints, application factories, extensions, or WSGI behavior | [Flask](references/flask.md) |
| HTTP or event contracts, validation, authentication, authorization, sessions, or webhooks | [contracts and security](references/contracts-and-security.md) |
| Database access, ORM lifecycle, transactions, schema changes, or data rollout | [data and migrations](references/data-and-migrations.md) |
| Sync/async ownership, concurrent updates, request context, or tenant isolation | [concurrency and tenancy](references/concurrency-and-tenancy.md) |
| Queues, schedulers, workers, WebSockets, or event delivery | [background and realtime](references/background-and-realtime.md) |
| Files, object storage, outbound calls, retries, rate limits, or caches | [files, cache, and integrations](references/files-cache-and-integrations.md) |
| Logging, metrics, tracing, readiness, shutdown, or resource ownership | [observability and lifecycle](references/observability-and-lifecycle.md) |
| Choosing focused backend evidence or a real dependency boundary | [testing](references/testing.md) |

## Complete and verify the assigned result

Make the smallest complete change across every affected location inside the assigned boundary. Keep non-trivial business rules independent of transport when the established architecture supports that separation. Validate untrusted data at the real runtime boundary, authorize the concrete action and resource server-side, and make transactions, retries, idempotency, context cleanup, cache invalidation, and side effects explicit when correctness depends on them.

Use the project's native commands and the smallest faithful failing evidence when a behavior change can be demonstrated before implementation. Then run the focused proof and the nearest relevant fast checks that protect the changed risk. Use a real database, broker, storage service, browser, or deployed boundary only when its semantics are the risk and the effective project instructions and current authority permit it.

Do not replace completion with TODOs, placeholders, weakened validation or assertions, skipped checks, suppressed failures, compatibility debris, or an unrecorded follow-up. State what was actually observed and every material verification gap.

Keep secrets out of source, logs, errors, fixtures, telemetry, serialized output, and command traces. Preserve unrelated work. When a concrete out-of-scope project problem remains, record or reconcile it through the available project problem route when authorized, then return to the assigned result without expanding the investigation.
