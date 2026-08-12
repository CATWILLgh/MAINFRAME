# Contracts, validation, and webhooks

- Preserve the project's HTTP status, error, pagination, serialization, and versioning contract. Do not impose one universal response envelope.
- Validate body, path, query, headers, and external payloads at their trust boundary with the established validator. Keep static types and runtime validation distinct.
- Update OpenAPI or Swagger when it is an owned contract. Use AJV, Prism, or generated-client checks when the project already relies on them; do not claim contract safety from documentation alone.
- Webhooks require signature verification where supported, replay protection or idempotency where duplicates matter, and quick acknowledgement when processing can be deferred.
- Add idempotency only where retries or duplicate delivery can cause harm. Do not require an idempotency key for every POST.
- Keep transport mapping separate from business outcomes when the same behavior has several entrypoints.
- Avoid leaking stack traces, SQL, ORM errors, credentials, or internal identifiers in public responses.

Sources:
- OpenAPI specification — https://spec.openapis.org/oas/latest.html
- OWASP Input Validation Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- NestJS OpenAPI — https://docs.nestjs.com/openapi/introduction
