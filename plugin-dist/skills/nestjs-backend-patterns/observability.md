# Observability — pino + OpenTelemetry

Current Node de facto stack. Pino is Fastify's default logger; NestJS / Express use it via wrappers (`nestjs-pino`, `pino-http`). OpenTelemetry-JS instruments traces + metrics. `pino-opentelemetry-transport` bridges logs into OTel.

## pino setup

```typescript
import { pino } from "pino";
export const logger = pino({
  level: process.env.LOG_LEVEL ?? "info",
  redact: ["req.headers.authorization", "req.headers.cookie", "*.password", "*.token"],
  formatters: { level: (label) => ({ level: label }) },
  timestamp: pino.stdTimeFunctions.isoTime,
});
```

- JSON output by default → structured logs → backend-side filtering and indexing.
- `redact` is critical — mask sensitive fields automatically; complements the secrets-handling discipline.
- Per-request child logger: `logger.child({ requestId, userId, orgId })` — bound context propagates without re-passing.

## NestJS integration — `nestjs-pino`

`LoggerModule.forRoot({ pinoHttp: { ... } })` replaces NestJS's default `Logger` with pino + auto request-logging. Inject `Logger` from `nestjs-pino` everywhere.

## Express integration — `pino-http`

```typescript
import pinoHttp from "pino-http";
app.use(pinoHttp({ logger, customLogLevel: (req, res, err) => err ? "error" : res.statusCode >= 400 ? "warn" : "info" }));
```

## OpenTelemetry — auto-instrumentation first

Package `@opentelemetry/auto-instrumentations-node` covers HTTP, DB drivers, Redis, BullMQ, Express / Fastify / NestJS — start spans for free:

```typescript
import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
new NodeSDK({ instrumentations: [getNodeAutoInstrumentations()] }).start();
```

Manual spans for business operations: `tracer.startActiveSpan("billing.charge", async (span) => { ... })`.

## Log/trace correlation

`pino-opentelemetry-transport` injects `trace_id` / `span_id` into every log line:

```typescript
const transport = pino.transport({ target: "pino-opentelemetry-transport" });
const logger = pino({ ... }, transport);
```

Logs → OTel collector → backend (Tempo + Loki, Datadog, Honeycomb). Logs become joinable with traces.

## Metrics

`@opentelemetry/api-metrics` for counters / histograms / gauges. Common backend metrics: `http_requests_total{status, route}`, `db_query_duration_seconds`, `queue_depth`, `active_tenants`.

## Sources

- pino — https://getpino.io/
- OpenTelemetry JS — https://opentelemetry.io/docs/languages/js/
- pino-opentelemetry-transport — https://github.com/pinojs/pino-opentelemetry-transport
