# Node server frameworks

Use the installed framework's current documentation and preserve its registration, lifecycle, error, validation, and encapsulation model.

## NestJS

- Trace module imports, providers, scopes, guards, pipes, interceptors, exception filters, and platform adapter before editing a controller or provider.
- Preserve the configured Express or Fastify adapter; their request, reply, middleware, upload, and lifecycle behavior are not interchangeable.
- Avoid changing provider scope unless per-request state requires it and the dependency-graph and runtime cost are understood.

## Express

- Trace router mounting and middleware order. Error handlers and authentication middleware depend on placement.
- Confirm behavior against the installed major, especially promise rejection, path matching, parsing, and error propagation.
- Complete or delegate every response path so requests cannot hang or expose internal errors.

## Fastify

- Respect plugin registration order, encapsulation, decorators, hooks, schemas, serializers, and lifecycle.
- Treat validation schemas as trusted application code; never compile user-provided schemas.
- Keep asynchronous authorization or database work out of initial schema validation and place it in the appropriate lifecycle hook.

For any framework, keep transport adapters thin when the project has an existing service or use-case boundary. Preserve the established public error and serialization contract rather than imposing a universal response envelope.

Current owning references: [NestJS documentation](https://docs.nestjs.com/), [Express error handling](https://expressjs.com/en/guide/error-handling/), and [Fastify reference](https://fastify.dev/docs/latest/Reference/).
