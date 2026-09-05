# Files, caches, and resilience

- Stream large uploads and downloads where supported; enforce size, type,
  naming, and authorization at the boundary.
- Treat object keys, metadata, presigned URLs, and deletion as application
  contracts. Keep credentials server-side and constrain presigned access.
- Set timeouts and cancellation for outbound HTTP. Retry only transient, safely
  repeatable operations with bounded backoff and jitter.
- Add circuit breakers or rate limits only for a demonstrated failure mode and
  define fallback behavior.
- Cache only with explicit ownership, key composition, tenant isolation, TTL,
  invalidation, and stale-data behavior. Never make a cache the sole durable
  source.
- Remember that in-memory caches are process-local and disappear on restart;
  distributed caches add infrastructure and consistency costs.
- Test the promised fallback, timeout, retry, invalidation, or file boundary
  without external infrastructure when a faithful local substitute exists.

Sources: [Node.js streams](https://nodejs.org/api/stream.html),
[AWS S3 JavaScript](https://docs.aws.amazon.com/sdk-for-javascript/v3/developer-guide/javascript_s3_code_examples.html),
[OWASP file upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).
