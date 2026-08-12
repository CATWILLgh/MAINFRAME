# Observability and lifecycle

- Preserve the project's logger and telemetry stack. Add a new library only when the assigned result requires it.
- Use structured logs with stable event names and useful correlation fields. Redact secrets, credentials, tokens, cookies, and sensitive personal data.
- Distinguish liveness from readiness. Readiness may reflect critical dependencies; liveness should not create restart loops because a remote dependency is unavailable.
- Handle process termination and framework shutdown hooks so servers stop accepting work, drain owned resources within a bound, and close pools, queues, and telemetry.
- Propagate request or job context through the project's established mechanism. Do not assume request-local state survives queues or background execution.
- Metrics and traces should answer a concrete operational question. Avoid high-cardinality labels and duplicated error reporting.
- Test lifecycle code deterministically where practical; do not require a live telemetry backend to prove local behavior.

Sources:
- Node.js process — https://nodejs.org/api/process.html
- NestJS lifecycle events — https://docs.nestjs.com/fundamentals/lifecycle-events
- OpenTelemetry JavaScript — https://opentelemetry.io/docs/languages/js/
