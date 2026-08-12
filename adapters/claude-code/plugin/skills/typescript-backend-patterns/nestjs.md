# NestJS, Express, and Fastify

- In NestJS, trace module registration, provider scope, guards, pipes, interceptors, and exception filters before editing a controller or provider.
- Keep controllers and transport adapters thin. Put reusable business behavior in a service or use case when the project already uses that separation.
- Preserve the configured Nest platform adapter. Express and Fastify request, reply, middleware, upload, and plugin behavior are not interchangeable.
- Avoid request-scoped providers unless per-request state actually requires them; scope changes affect the dependency graph and runtime cost.
- Validate at the inbound boundary with the project's established mechanism, including transformation behavior and unknown-field policy.
- Map domain and persistence failures to the project's existing error contract. Do not invent a universal envelope or status-code policy.
- For new standalone HTTP code, use the project's chosen framework consistently; do not add NestJS merely because this skill supports it.

Sources:
- NestJS documentation — https://docs.nestjs.com/
- Express documentation — https://expressjs.com/
- Fastify documentation — https://fastify.dev/docs/latest/
