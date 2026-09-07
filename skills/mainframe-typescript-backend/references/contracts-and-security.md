# Contracts and security

## Runtime contracts

- Preserve established status codes, errors, pagination, serialization, versioning, and event shapes. Do not impose a universal response envelope.
- Keep static TypeScript types distinct from runtime validation. Validate untrusted bodies, paths, queries, headers, form data, events, job payloads, and external responses at their actual trust boundary.
- Update OpenAPI, GraphQL, event schemas, generated clients, or contract tests when the project owns them and the change affects their contract.
- Separate transport mapping from business outcomes when the behavior has multiple entrypoints.
- Never expose stack traces, SQL or ORM errors, credentials, internal filesystem paths, or internal-only identifiers through public responses.

## Authentication and authorization

- Preserve the established trust model. Sessions, signed tokens, OAuth or OIDC, API keys, and service credentials have different verification, renewal, revocation, and storage semantics.
- Verify credentials using the protocol and installed library; decoding or parsing alone is not authentication.
- Derive identity and tenant context from verified credentials or server-owned state. Treat caller-supplied identity fields as untrusted input.
- Authorize the concrete action and resource near the protected operation or data boundary. Authentication, route visibility, middleware, and hidden UI controls are not sufficient authorization by themselves.
- Preserve cookie, CSRF, rotation, logout, revocation, origin, and replay protections that apply to the established mechanism.

## Webhooks and retries

- Verify signatures and freshness when the provider supports them. Preserve the raw-byte boundary when signature verification depends on it.
- Assume duplicate delivery. Add a stable idempotency boundary when repeated effects can cause harm.
- Acknowledge only after the required durability point; defer work only when the durable handoff and failure behavior are established.

Current owning references: [OpenAPI specification](https://spec.openapis.org/oas/latest.html), [OWASP input validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html), [OWASP authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), and [OWASP authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).
