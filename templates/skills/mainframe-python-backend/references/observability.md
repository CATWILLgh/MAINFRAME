# Observability

Preserve the project's logging, metrics, tracing, and error-reporting pipeline. Do not introduce structlog, OpenTelemetry, Sentry, or Prometheus merely because this reference covers them.

## Useful signals

- Emit structured, stable event names and fields through the existing logger. Include correlation identifiers already supported by the runtime.
- Record outcomes and durations for important external or business operations without logging complete payloads.
- Use bounded-cardinality metric labels. User, tenant, request, entity, URL, and exception-message values usually do not belong in metric labels.
- Add manual spans only around meaningful work not already represented by framework or client instrumentation.
- Preserve exception causality and distinguish expected domain rejection from operational failure.

## Sensitive data

Treat request and response bodies, credentials, cookies, authorization headers, database URLs, personal data, and arbitrary query values as sensitive. Prefer an allowlist of safe fields and central filtering at the logging or telemetry boundary.

## Library branches

- With stdlib logging, preserve configured handlers and structured formatting rather than adding a parallel pipeline.
- With structlog, bind request context through its supported context mechanism and configure processors once at startup.
- With OpenTelemetry, verify compatible instrumentation versions and exporter ownership before enabling automatic instrumentation; duplicate instrumentation can emit duplicate spans.
- With Sentry or another error reporter, inspect scrubbing, environment, release, and sampling configuration before adding captured context.

## Sources

- Python logging — https://docs.python.org/3/library/logging.html
- structlog — https://www.structlog.org/en/stable/
- OpenTelemetry Python — https://opentelemetry.io/docs/languages/python/
- OpenTelemetry metrics — https://opentelemetry.io/docs/specs/otel/metrics/api/
