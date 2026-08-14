# NestJS, Express, and Fastify

- In NestJS, trace module registration, provider scope, guards, pipes,
  interceptors, and exception filters before editing controllers or providers.
- Keep transport adapters thin. Put reusable business behavior in the existing
  service or use-case boundary when the project has one.
- Preserve the configured Nest platform adapter. Express and Fastify request,
  reply, middleware, upload, and plugin behavior are not interchangeable.
- Avoid request-scoped providers unless per-request state requires them; scope
  changes affect the dependency graph and runtime cost.
- Validate inbound data with the project's established transformation and
  unknown-field policy.
- Map domain and persistence failures to the existing error contract. Do not
  invent a universal envelope or status-code policy.
- Keep a new standalone service on its chosen framework consistently. Do not
  add NestJS merely because this skill supports it.

Sources: [NestJS](https://docs.nestjs.com/),
[Express](https://expressjs.com/),
[Fastify](https://fastify.dev/docs/latest/).
