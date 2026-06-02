# Observability — structlog + OpenTelemetry

Current de-facto stack for enterprise Python backends. Three separate signals: structured logs, distributed traces, metrics — each with its own pipeline, joined at the observability backend.

## structlog setup

- `structlog.get_logger()` per module, top of file. NOT a singleton at app level.
- Configure once at startup (in `create_app()` / `lifespan`): JSON renderer for production, console renderer for dev.
- Add processors for `add_log_level`, `add_logger_name`, timestamp, exception formatting.
- Bind request-scoped context (`request_id`, `user_id`, `org_id`) once per request and let structlog propagate it.

```python
import structlog
logger = structlog.get_logger()
logger.info("job.create", job_id=j.id, org_id=org.id, duration_ms=dt)
```

## OpenTelemetry — auto-instrumentation first

- Per dash0/OTel docs: "The OpenTelemetry LoggingHandler connects Python's familiar logging API to the OTel ecosystem, and every logging call flows into your observability pipeline as a first-class OTel log record, with trace context, typed attributes, and resource metadata attached."
- Add framework auto-instrumentation: `opentelemetry-instrumentation-{fastapi,flask,django,sqlalchemy,requests}`. Picks up spans for free.
- Manual spans for business operations: `tracer.start_as_current_span("billing.charge")` around the operation that matters to the user.

## Trace correlation in logs

- Configure structlog to inject `trace_id` / `span_id` from current OTel span.
- Logs become joinable to traces in the backend (Grafana Tempo + Loki, Datadog, Honeycomb).

```python
def add_trace_ids(_, __, event_dict):
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
    return event_dict
```

## Sensitive data masking

- Never log raw request bodies — credentials, PII, tokens may be inside.
- Whitelist fields explicitly: `logger.info("user.login", email_hash=hash(email), org_id=org_id)`, not `**request.json`.
- Mask Authorization headers, cookies, query strings with secrets. Centralised mask helper, applied at the log boundary.

## Metrics

- Counters: `requests_total{status,route}`, `errors_total{type}`.
- Histograms: latency per route, DB query duration.
- Active gauges: tenant count, queue depth.
- Prometheus exposition via `prometheus_client` (sync) or `opentelemetry-exporter-prometheus`.

## Sources

- structlog docs — https://www.structlog.org/en/stable/
- OpenTelemetry Python — https://opentelemetry.io/docs/languages/python/
- Dash0 — https://www.dash0.com/guides/opentelemetry-logging-python
