# Files, cache, and integrations

Treat filenames, MIME types, archive members, object keys, URLs, redirects, and remote responses as untrusted input. Enforce size and time bounds, prevent traversal and server-side request forgery, and use atomic or staged writes where partial output would be harmful.

For object storage and signed URLs, preserve ownership, expiry, content constraints, and cleanup semantics. Do not make private data public as a shortcut. Avoid logging signed URLs, credentials, or sensitive object metadata.

For outbound HTTP, use the project's established client and lifecycle. Set bounded connect, read, write, and pool behavior appropriate to the operation. Retry only safe or idempotent operations with bounded backoff and a termination condition; respect rate limits and surface exhausted retries clearly.

Treat external schemas and generated clients as contracts. Validate remote data before it reaches business logic. Determine whether generated code is canonical or derived, and verify the consumer after regeneration.

Use cache only when it is already part of the design or explicitly required. Define the source of truth, key scope including tenant boundaries, expiry, invalidation, stampede behavior, serialization compatibility, and failure mode. Redis is one possible implementation, not a default.
