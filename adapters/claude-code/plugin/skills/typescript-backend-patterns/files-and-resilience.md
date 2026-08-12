# Files, caches, and resilience

- Stream large uploads and downloads where supported; enforce size, type, naming, and authorization at the boundary. Do not buffer unbounded user files in memory.
- Treat S3 or MinIO object keys, metadata, presigned URLs, and deletion as application contracts. Keep credentials server-side and constrain presigned capabilities and expiry.
- For outbound HTTP, set timeouts and cancellation. Retry only transient, safely repeatable operations with bounded backoff and jitter.
- Use circuit breakers or rate limits only for a demonstrated failure mode and define fallback behavior. A library alone does not create resilience.
- Cache only when ownership, key composition, tenant isolation, TTL, invalidation, and stale-data behavior are explicit. Do not make a cache the sole durable source.
- In-memory LRU caches are process-local and disappear on restart; distributed caches add infrastructure and consistency costs. Choose from the actual contract.
- Test the fallback, timeout, retry, invalidation, or file boundary that the changed behavior promises without requiring external infrastructure when a faithful local substitute exists.

Sources:
- Node.js streams — https://nodejs.org/api/stream.html
- AWS S3 JavaScript examples — https://docs.aws.amazon.com/sdk-for-javascript/v3/developer-guide/javascript_s3_code_examples.html
- OWASP File Upload Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
