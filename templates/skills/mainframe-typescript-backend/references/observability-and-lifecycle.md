# Observability and lifecycle

- Preserve the project's logger and telemetry stack unless the assigned result
  requires a change.
- Use structured logs with stable event names and useful correlation fields.
  Redact secrets, tokens, cookies, credentials, and sensitive personal data.
- Distinguish liveness from readiness. A remote dependency failure should not
  create a liveness restart loop.
- Handle process termination and framework shutdown so servers stop accepting
  work, drain owned resources within a bound, and close pools, queues, and
  telemetry.
- Propagate request or job context through the existing mechanism. Request-local
  state does not automatically survive queues or background work.
- Add metrics and traces for a concrete operational question. Avoid
  high-cardinality labels and duplicate error reporting.
- Test lifecycle behavior deterministically without a live telemetry backend
  when practical.

Sources: [Node.js process](https://nodejs.org/api/process.html),
[NestJS lifecycle](https://docs.nestjs.com/fundamentals/lifecycle-events),
[OpenTelemetry JavaScript](https://opentelemetry.io/docs/languages/js/).
