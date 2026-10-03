# Event-to-recipient delivery

## Explicit contract

Define a stable event ID/type/schema version, occurrence time, resource reference,
tenant and immutable recipient identity. Keep event data minimal and authorized
for its destination. A missing recipient is an error or explicit no-recipient
outcome, never an implicit broadcast. Define subscriptions/consent and event
selection before dispatch, and recheck current access before a deferred send.

Separate event identity from an attempt ID. Identify a logical delivery by event,
channel, destination identity and any rendered part; persist unique constraints
or equivalent deduplication. Retry preserves the logical ID. Snapshot routing
and content/config revisions as needed for audit, while using current authorized
credentials and stop policy. Editing a recipient must not redirect old sensitive
jobs; explicitly cancel/replan them under policy. Unknown event/channel names
fail validation, never fall back to Telegram or a default broadcast.

## Durability proportionate to consequence

Reuse the existing job system. For events that must survive restart, commit an
outbox/job alongside the business change and dispatch asynchronously. An existing
relational database can be sufficient; do not add infrastructure reflexively.
A background in-memory queue is acceptable only for explicitly disposable/best-
effort notifications with documented loss, visible dropped counts and bounded
memory. A warning log does not turn a dropped critical event into reliable delivery.

Workers claim bounded batches with leases/ownership and recover abandoned work.
Fence stale workers when updating state; a database lease alone cannot stop a
provider request already in flight. Bound concurrency, channel/destination rate,
queue age and attempt time. One stalled destination must not block unrelated
channels. Avoid unbounded goroutines and whole-recipient-list loading. Shut down
by stopping claims, handling in-flight work and leaving recoverable jobs.

For related events, choose ordering or explicit sequence/version rules so a late
"opened" cannot overwrite "resolved". Coalescing, digests and notification tags
are explicit policies, not generic deduplication. Never coalesce across tenants,
resources or recipients. Retry only failed destinations/parts, not the whole fan-out.

## Outcomes and retries

| State | Meaning |
| --- | --- |
| Queued / retry scheduled | Persisted intent; not sent |
| Suppressed / cancelled / expired / no recipients | No send under explicit policy; not success |
| Provider accepted | A valid provider-specific acknowledgement was received |
| Outcome unknown | Request may have been accepted, but acknowledgement/persistence is uncertain |
| Failed permanently | Proven terminal rejection, invalid config or exhausted retries with known rejection |
| Delivered / read | Only when a channel exposes and the app verifies that specific receipt |

Classify transport failures by whether submission could have occurred. Do not
blindly retry a non-idempotent send after timeout or a lost acknowledgement.
Where a provider supports an idempotency key, persist/reuse it. Otherwise choose
the event's agreed duplicate-versus-loss policy, reconcile if possible, and show
unknown outcomes. Exactly-once end-to-end is not guaranteed by a queue unique key,
Message-ID, lease or provider message ID learned only after the response.

Retry known transient/retryable failures with bounded exponential backoff and
jitter, respecting provider retry delays, job age and attempt limits. Do not
retry bad credentials, invalid recipients/content or unsupported operations as
ordinary transient errors. Re-enqueue delays rather than sleeping inside scarce
workers. After the last failure, do not sleep once more. Retain an actionable
failure state and an audited controlled replay route. Exhausting attempts does not
turn an unknown acceptance into a proven failure.

## Switches, security and evidence

Define the master off behavior for pending work: cancel, expire or retain paused
jobs. Re-enabling must not unleash an accidental stale flood. All workers check
master/channel/event policy before each external attempt; in-flight accepted
messages cannot be recalled. Show any separate test bypass explicitly, or honor
the switches for tests. Saved settings, not unsaved UI drafts, govern normal sends.

Bound HTTP/SMTP connection/read/write/response sizes and actually cancel network
IO, not just the caller's wait. Validate arbitrary endpoints at connection time,
including resolved addresses and redirects, and retain TLS verification. Allow
specific authorized private destinations when required, not unrestricted private
network access. Never emit credential-bearing URLs or raw provider errors to logs.

Protect settings, test sends, manual replay and registration by role/tenant and
CSRF/origin policy. Keep secret-present indicators and explicit keep/replace/clear
operations. Do not treat any value containing mask bullets as "unchanged". Audit
metadata/actions with redacted fields, bounded retention and access control.
Distinguish storage failure from disabled/no recipients; expose a configuration
load error instead of silently discarding the event.
