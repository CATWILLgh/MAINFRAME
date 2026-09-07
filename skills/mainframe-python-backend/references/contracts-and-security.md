# Contracts and security

Identify the real boundary: HTTP, RPC, event, webhook, worker payload, CLI, or internal call. Preserve method, route, status, headers, content type, schema, pagination, ordering, error envelope, compatibility policy, and idempotency behavior unless changing them is assigned.

Validate untrusted input at runtime with the framework or library already owning that boundary. Distinguish omitted, null, empty, defaulted, coerced, and invalid values. Do not confuse annotations or ORM models with an external validation contract. Prevent internal models, secrets, and implementation-only fields from leaking through serialization.

Authenticate the presented credential and authorize the exact action on the exact resource. Derive tenant, organization, ownership, role, and scope constraints server-side. Treat OAuth, OIDC, JWT, API keys, cookies, and sessions according to their actual issuer, audience, expiry, rotation, revocation, and transport model; do not invent missing policy.

For cookie-backed mutation, preserve or establish the project's CSRF and same-site boundary. For browser clients, keep CORS and credential rules explicit. For uploads and redirects, validate size, type, destination, and trust boundaries rather than trusting names or client metadata.

For webhooks and retried mutations, verify signatures over the correct bytes, enforce freshness where the protocol requires it, deduplicate with a stable identity, and define safe replay behavior. Do not log credentials, session material, raw authorization headers, signed URLs, or sensitive payloads.
