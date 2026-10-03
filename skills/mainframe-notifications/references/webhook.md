# Generic outbound webhooks

This is an application-to-receiver HTTP event contract, not a synonym for the
Bitrix24 incoming webhook used to authorize REST calls. Establish the receiver's
schema, authentication, acknowledgement and idempotency semantics before coding.
Reuse an existing contract; do not force a new signing scheme on an existing API.

For a new controlled receiver, prefer a documented established scheme such as
[Standard Webhooks](https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md).
Its signed input combines the stable webhook ID, timestamp and exact raw payload;
headers include `webhook-id`, `webhook-timestamp` and `webhook-signature`. Use a
maintained compatible implementation rather than inventing cryptography. Both
sides agree version/key encoding, signed bytes, timestamp tolerance and rotation.
A retry keeps logical ID/payload and signs its current attempt timestamp. The
receiver verifies before processing, durably deduplicates for the whole retry/
replay horizon, and acknowledges only after its agreed durable handoff. Do not
copy a short example dedup TTL when retries can continue for days.

Define bounded versioned payloads with event time distinct from send time. Give
consumers examples and schema, ordering expectations and unknown-field behavior.
Select fields by destination authorization; avoid full-record dumps. Use HTTPS,
fixed content type and limits. Treat endpoint URLs and signing keys as sensitive.
Rotate with overlapping key verification when the contract supports it; never
log signatures or full capability URLs.

Apply [OWASP SSRF controls](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
to registration, test and every retry: approved scheme/port/destination, DNS and
actual connection address validation, redirect restrictions and network egress
policy. Disable redirects by default; explicitly authorized redirects need fresh
validation and must not forward secrets to a new authority. Private receivers
need a specific approved policy, not a blanket private-network exception.

Classify responses under [HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html)
and the receiver's contract. A 2xx acknowledges only its defined stage, not the
business side effect. Honor valid Retry-After without exceeding job lifetime;
a 202 may mean queued, and a 409 may mean duplicate or actual conflict. Do not
infer either from status alone. Do not retry arbitrary 4xx; bound retryable 429/
5xx responses. A timeout after submission is unknown, not proven rejection;
retry automatically only under the agreed dedup/duplicate policy.

Test byte-exact signatures, body mutation, stale timestamps, overlap rotation,
repeat IDs, accepted-but-response-lost, redirects/DNS changes, size limits and
unauthorized tenant destinations. Public webhook standards do not verify a
particular receiver: its actual contract and authorized acceptance still matter.

Sources reviewed 2026-10-03. Standard Webhooks is a community specification,
not universal behavior imposed by HTTP or every webhook provider.
