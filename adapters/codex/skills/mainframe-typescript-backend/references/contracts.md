# Contracts, validation, and webhooks

- Preserve HTTP status, errors, pagination, serialization, and versioning. Do
  not impose a universal response envelope.
- Validate body, path, query, headers, and external payloads at their trust
  boundary. Keep static TypeScript types distinct from runtime validation.
- Update OpenAPI or Swagger when it is an owned contract. Existing generated
  clients or contract checks are stronger evidence than prose alone.
- Verify webhook signatures where supported, protect against replay or
  duplicates where they can cause harm, and acknowledge quickly when durable
  processing can be deferred.
- Add idempotency where retries or duplicate delivery can cause harm, not to
  every POST by default.
- Separate transport mapping from business outcomes when behavior has several
  entrypoints.
- Never expose stack traces, SQL, ORM errors, credentials, or internal-only
  identifiers through public responses.

Sources: [OpenAPI](https://spec.openapis.org/oas/latest.html),
[OWASP input validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html),
[NestJS OpenAPI](https://docs.nestjs.com/openapi/introduction).
