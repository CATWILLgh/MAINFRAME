# Signals and collection

Keep application liveness, readiness, dependency health and user-facing function
separate. A successful database ping is not transaction correctness; a running
container is not a healthy service. A diagnostics endpoint may return a partial
successful envelope while one collector failed, but authentication failures and
invalid requests retain their normal error semantics. Do not reuse that envelope
as a readiness/liveness response without the deployment's explicit contract.

Represent each observation with source/resource, observed_at, status and freshness.
Use nullable values and a reason for unsupported, unavailable or denied data.
Preserve the last successful sample only with its original timestamp and a stale
marker. A timeout is not zero CPU, an empty database or proof the service is down.
Avoid converting absent values to zero in serialization or charts.

Document metric units and denominators: process versus container versus host
memory, working set versus total, CPU interval and core normalization. Counter
resets after restart are not negative traffic. Do not calculate rates from one
sample or mix samples across resource generations. Collection timing and clock
skew affect freshness; use monotonic durations where available.

Reuse existing telemetry. Bound per-collector timeout, overall deadline,
concurrency, response bytes, sample count, retention and resource cardinality.
Cache/coalesce collection across viewers; avoid polling every dependency afresh
for every open browser. Paginate inventories and cap log tails before buffering.
Cancel actual IO on client cancellation/shutdown. Streaming logs need bounded
buffers, disconnect handling and redaction, not unlimited accumulation.

Isolate slow/failing collectors so one dependency does not hold the whole page.
Back off repeated failures, prevent overlapping refreshes and pause browser polling
when hidden as appropriate. Do not trigger extra collection recursively through
telemetry about the collector itself. Probe only configured authorized dependencies;
never accept arbitrary URLs/queries supplied by page users.

Preserve enough local diagnostic information to explain a dependency failure
without leaking credentials, payloads or raw connection strings. Scope cached
results by environment and authorization; do not share privileged samples with a
less privileged viewer. Authentication and authorization also apply to downloads
and streaming endpoints.

Platform-specific metric and health semantics must be verified against the deployed
versions. Useful primary references (reviewed 2026-10-04):

- [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/)
- [Kubernetes probe distinctions](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/)
