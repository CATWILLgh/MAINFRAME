# Integrations and resilience

Use the established client and inject the narrow transport or endpoint needed
for tests. Build requests with the caller's context, set bounded operation and
transport timeouts, close response bodies, validate status and content type,
limit reads, and validate remote schemas before they enter business logic.

Classify operations by replay safety. Retry safe reads only with a bounded
policy, backoff/jitter as appropriate, rate-limit handling, and a termination
condition. For mutations, use the provider's stable idempotency identity when
available. A timeout, connection loss, HTTP 408, or server error after dispatch
may mean the provider accepted the operation; do not convert that ambiguity to
local success or blindly send again.

When duplicate external effects are materially harmful, persist admission or an
attempt identity before dispatch. Retain `pending` or `unknown` across rollback
and restart, fence later sends, and require an authorized compare-and-set
reconciliation against current business state. Commit confirmed outcome,
business-state change, and audit together. Keep simulated crash recovery
separate from an actual process-kill test and local mocks separate from live
provider acceptance.

Keep provider-specific payloads, pagination, errors, and credentials behind an
adapter. Normalize only facts the source actually supplies; preserve unknown
states rather than guessing from names. Store raw payloads only for a defined
diagnostic or audit need with an explicit retention and privacy boundary.

For rate gates, caches, and circuit breakers, define sharing scope, key identity,
clock source, cancellation, persistence, and multi-process behavior. Process
memory is not a distributed guarantee.
