---
name: mainframe-logging
description: Application logging and error diagnostics. Define or repair structured events, request/job correlation, failure context, redaction, and coverage.
---

# Application logging

Start with the operation someone needs to diagnose and the decision the log
should support. Find the existing logger, access logs, error reporting, and
correlation at the affected boundary. Apply the baseline to the new or changed
events. Reuse existing fields and sinks. If a project uses different names,
types, or formatting, map the common meanings at its existing boundary and
keep the mapping with the project's logging guidance. For example, map
`ts`, `severity`, and `msg` to `timestamp`, `level`, and `message` while
preserving the names consumed by existing tools. Resolve material conflicts
with the project owner.

## Common event fields

Use structured fields for new events. Existing serializers may provide
equivalent fields, and trusted deployment or collector metadata may supply the
emitter identity.

| Field | Meaning |
| --- | --- |
| `timestamp` | UTC event time, in RFC 3339 when serialized as text |
| `level` | `DEBUG` for bounded diagnostics, `INFO` for normal outcomes, `WARN` for recoverable degradation, `ERROR` for unexpected failures requiring investigation. Map additional native levels by meaning |
| `event`, `message` | Stable event name such as `stock.update.completed` and a short, safe human-readable summary |
| `service`, `environment`, `version` | Stable component identity, deployment environment when applicable, and actual release identity when available |
| `request_id`, `job_id` or `operation_id` | Applicable opaque correlation from the owning context. Carry it across queue and retry boundaries |
| `trace_id`, `span_id` | Active trace context when available. In JSON use top-level lowercase hexadecimal values from the tracing context |
| `outcome`, `duration_ms` | Actual result and elapsed monotonic time at the event boundary. For terminal results use `success`, `rejected`, `failed`, `cancelled`, `skipped`, or `unknown` as applicable, or map equivalent existing values |
| `phase`, `error_kind`, `error_code` | On relevant failures, the observed phase, stable error category, and useful safe code such as SQLSTATE or upstream status |

Keep event names independent of runtime IDs and values. Use event-specific
typed fields only where they explain the outcome. For example, a failed
`stock.update.completed` event can carry
`phase=db_lock`, `error_kind=lock_timeout`, `error_code=55P03`, and
`duration_ms=502`. Record the most specific phase the application actually
observed. A database timeout alone does not identify the lock holder.

## Cover the operation

Record significant lifecycle and operation outcomes, actionable dependency
degradation or recovery, and the project's required security events. At the
boundary that knows the outcome, record a failure once with causal context.
Keep separately useful retry or recovery events correlated and bounded. Reuse
existing request or job summaries. Use aggregate metrics for routine volume
and timing where available, with IDs in logs or traces rather than metric labels.

For asynchronous work, distinguish acceptance, queue delay, and completion.
Record an ambiguous external result as `unknown` until reconciled.
For a slow or failed request, make relevant phases distinguishable, such as
pool acquisition, database execution, lock wait, and an upstream call. Expose
actionable product state to users and keep operational detail in diagnostics.

## Protect data and service capacity

Allowlist fields before emission, including on exception paths. Use bounded
values and structured encoding for untrusted input. Exclude secrets, session
material, protected personal data, raw payloads, secret-bearing URLs, SQL
parameters, and unreviewed exception or request objects. Preserve enough safe
context to diagnose the failure.

Reuse the existing logging delivery, rotation, access and retention controls.
Bound volume and buffering and avoid a synchronous network dependency in the
request or transaction path. Ordinary logging sink failure should leave
application work available. Apply the project's durability and access
requirements to mandatory audit records separately.

## Verify the emitted records

Capture records through the real logger on a representative success and
failure. Check the event, outcome, safe phase and correlation. Exercise the
async or retry boundary if changed. Pass a synthetic sensitive value and
verify it is absent from the emitted record, including error context. If
changing the logging delivery, check sink failure and resource bounds.

This baseline maps to the stable [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/#log-and-event-record-definition)
and [trace context compatibility](https://opentelemetry.io/docs/specs/otel/compatibility/logging_trace_context/#json-formats).
Event coverage, safe fields and delivery checks follow the
[OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html).
The field names above are MAINFRAME defaults for application logs.
