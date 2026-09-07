# Observability and lifecycle

- Preserve the project's logger, metrics, tracing, error-reporting, and correlation mechanisms unless changing one belongs to the task.
- Use stable structured events and only fields needed to answer an operational question. Redact credentials, tokens, cookies, secret-bearing URLs, sensitive personal data, and protected payloads.
- Avoid high-cardinality labels, duplicate reporting of the same failure, and telemetry that changes business behavior or leaks tenant boundaries.
- Distinguish liveness, readiness, startup completion, and degraded dependency state. A remote dependency outage should not automatically create a liveness restart loop.
- Give each long-lived resource one owner. On termination, stop accepting new work, bound drain behavior, and close servers, pools, workers, queues, sockets, file handles, and telemetry in the framework's supported order.
- Preserve request or job correlation across the actual async boundary. Process-local context does not automatically survive queues, schedulers, or external events.
- Keep startup and shutdown repeatable under development reloads and test isolation. Do not register duplicate handlers, consumers, timers, or exporters.
- Test lifecycle and observability behavior deterministically without a live telemetry backend when the external backend is not the risk.

Current owning references: [Node.js process documentation](https://nodejs.org/api/process.html), [NestJS lifecycle events](https://docs.nestjs.com/fundamentals/lifecycle-events), and [OpenTelemetry JavaScript](https://opentelemetry.io/docs/languages/js/).
