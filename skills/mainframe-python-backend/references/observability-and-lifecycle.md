# Observability and lifecycle

Use the shared [logging baseline](../../mainframe-logging/SKILL.md) with the
project's existing logger and error reporting. Keep metric labels bounded and
propagate correlation across requests, jobs, outbound calls and realtime events.

Make failure reasons actionable at the owning boundary. Do not swallow exceptions, convert every failure into a generic success, or log the same exception repeatedly at multiple layers. Keep expected domain failures distinct from dependency, programming, and cancellation failures.

Distinguish liveness from readiness. Readiness should reflect only dependencies required to accept meaningful work and should not perform destructive or unbounded checks. A process responding to HTTP does not prove migrations, workers, queues, or external integrations are usable.

Own long-lived resources at the process or application lifecycle that creates them. Initialize them once per intended process, close them during graceful shutdown, and avoid duplicate startup work under reloaders, prefork servers, tests, or repeated application-factory calls.

Verify WSGI or ASGI server behavior, worker count, preload or reload mode, signal handling, shutdown grace, and in-flight work where lifecycle is part of the risk. Do not infer production behavior from an in-process test client alone.
