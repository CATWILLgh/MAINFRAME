# Files, cache, and resilience

## Files and object storage

- Enforce authorization, size, content, naming, and lifecycle constraints at the real upload or download boundary. Do not trust filenames or client MIME declarations as proof of safe content.
- Stream large content when buffering would create material memory or latency risk. Preserve cancellation and partial-failure behavior.
- Treat object keys, metadata, retention, presigned access, and deletion as application contracts. Keep storage credentials server-side and constrain temporary access to its required resource, operation, and lifetime.

## Outbound calls

- Set explicit connection and operation timeouts and propagate cancellation when supported.
- Retry only failures that are plausibly transient and only when the operation is safely repeatable or protected by an idempotency identity. Bound attempts and backoff.
- Preserve the service's error, fallback, and partial-success contract. Add circuit breakers, bulkheads, or rate limits only for a demonstrated risk with defined recovery behavior.
- Validate external responses before using them as trusted internal state. Keep credential-bearing headers, URLs, bodies, and traces out of logs and errors.

## Cache

- Define cache ownership, key composition, tenant isolation, serialization, TTL, invalidation, staleness, miss, and outage behavior before changing cached data.
- Never make a cache the sole durable source. Confirm whether a process-local cache remains correct across replicas and restarts before using one.
- Distributed caches introduce infrastructure and consistency costs; do not add one without a project decision that requires it.

Test the promised timeout, retry, cancellation, invalidation, file, or fallback boundary with the cheapest faithful observation. Use a real external service only when its own protocol or runtime behavior is the risk and access is authorized.

Current owning references: [Node.js streams](https://nodejs.org/api/stream.html), [AWS SDK for JavaScript S3 examples](https://docs.aws.amazon.com/sdk-for-javascript/v3/developer-guide/javascript_s3_code_examples.html), and [OWASP file upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).
